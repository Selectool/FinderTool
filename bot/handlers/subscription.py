"""
Обработчики подписки и платежей с интеграцией ЮKassa
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.universal_database import UniversalDatabase
from bot.keyboards.inline import get_subscription_keyboard, get_back_keyboard
from services.payment_service import create_payment_service
from bot.utils.production_logger import log_user_action, log_payment, handle_error
from config import (TEXTS, SUBSCRIPTION_PRICE, YOOKASSA_PROVIDER_TOKEN,
                   YOOKASSA_CURRENCY, YOOKASSA_PROVIDER_DATA)
import logging

logger = logging.getLogger(__name__)
router = Router()


class PaymentStates(StatesGroup):
    """Состояния для процесса оплаты"""
    waiting_payment = State()


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, db: UniversalDatabase):
    """Команда подписки"""
    user_id = message.from_user.id
    is_subscribed = await db.check_subscription(user_id)
    
    if is_subscribed:
        await message.answer(
            "💎 <b>У вас уже есть активная подписка!</b>\n\n"
            "Используйте /profile для просмотра деталей.",
            parse_mode="HTML"
        )
        return
    
    await message.answer(
        TEXTS["subscription_info"].format(price=SUBSCRIPTION_PRICE),
        parse_mode="HTML",
        reply_markup=get_subscription_keyboard()
    )


@router.callback_query(F.data == "subscribe")
async def callback_subscribe(callback: CallbackQuery, db: UniversalDatabase):
    """Callback подписки"""
    user_id = callback.from_user.id
    is_subscribed = await db.check_subscription(user_id)
    
    if is_subscribed:
        await callback.message.edit_text(
            "💎 <b>У вас уже есть активная подписка!</b>\n\n"
            "Используйте /profile для просмотра деталей.",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        TEXTS["subscription_info"].format(price=SUBSCRIPTION_PRICE),
        parse_mode="HTML",
        reply_markup=get_subscription_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "pay_subscription")
async def callback_pay_subscription(callback: CallbackQuery, db: UniversalDatabase, state: FSMContext):
    """Callback оплаты подписки через ЮKassa"""
    user_id = callback.from_user.id

    try:
        # Проверяем, что у пользователя нет активной подписки
        is_subscribed = await db.check_subscription(user_id)
        if is_subscribed:
            await callback.message.edit_text(
                "💎 <b>У вас уже есть активная подписка!</b>\n\n"
                "Используйте /profile для просмотра деталей.",
                parse_mode="HTML",
                reply_markup=get_back_keyboard()
            )
            await callback.answer()
            return

        # Создаем сервис платежей
        payment_service = create_payment_service(
            provider_token=YOOKASSA_PROVIDER_TOKEN,
            currency=YOOKASSA_CURRENCY,
            provider_data=YOOKASSA_PROVIDER_DATA,
            db=db
        )

        # Показываем информацию о тестовой карте если в тестовом режиме
        test_card_info = payment_service.get_test_card_info()
        if test_card_info:
            await callback.message.edit_text(
                f"💳 <b>Тестовый режим оплаты</b>\n\n"
                f"{test_card_info}\n\n"
                f"Создаю инвойс для оплаты...",
                parse_mode="HTML"
            )

        # Создаем данные для инвойса
        amount_in_kopecks = SUBSCRIPTION_PRICE * 100  # Конвертируем в копейки

        logger.info(f"Создание инвойса для пользователя {user_id}:")
        logger.info(f"  - Цена подписки: {SUBSCRIPTION_PRICE} ₽")
        logger.info(f"  - Сумма в копейках: {amount_in_kopecks}")

        invoice_data = await payment_service.create_invoice_data(
            user_id=user_id,
            amount=amount_in_kopecks,
            description=f"Подписка FinderTool - {SUBSCRIPTION_PRICE}₽/месяц",
            subscription_months=1
        )

        # Устанавливаем состояние ожидания платежа
        await state.set_state(PaymentStates.waiting_payment)

        logger.info(f"Отправка инвойса пользователю {user_id}")

        # Отправляем инвойс
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            **invoice_data
        )

        await callback.answer("Инвойс создан!")
        logger.info(f"✅ Инвойс успешно отправлен пользователю {user_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка при создании инвойса для пользователя {user_id}: {e}")
        logger.error(f"Детали ошибки: {str(e)}")

        # Более детальная информация об ошибке
        error_message = "❌ <b>Ошибка при создании платежа</b>\n\n"

        if "provider_token" in str(e).lower():
            error_message += "Проблема с настройкой платежной системы.\n"
        elif "amount" in str(e).lower():
            error_message += "Проблема с суммой платежа.\n"
        else:
            error_message += "Временная техническая проблема.\n"

        error_message += "Попробуйте позже или обратитесь к администратору."

        await callback.message.edit_text(
            error_message,
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        await callback.answer("Произошла ошибка!")


# Обработчики платежей ЮKassa

@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery, db: UniversalDatabase):
    """Обработка предварительной проверки платежа"""
    try:
        # Создаем сервис платежей
        payment_service = create_payment_service(
            provider_token=YOOKASSA_PROVIDER_TOKEN,
            currency=YOOKASSA_CURRENCY,
            provider_data=YOOKASSA_PROVIDER_DATA,
            db=db
        )

        # Проверяем платеж
        is_valid = await payment_service.process_pre_checkout(pre_checkout_query)

        # Отвечаем на предварительную проверку
        await pre_checkout_query.answer(ok=is_valid)

        if is_valid:
            logger.info(f"Предварительная проверка платежа прошла успешно: {pre_checkout_query.invoice_payload}")
        else:
            logger.warning(f"Предварительная проверка платежа не прошла: {pre_checkout_query.invoice_payload}")

    except Exception as e:
        logger.error(f"Ошибка при предварительной проверке платежа: {e}")
        await pre_checkout_query.answer(ok=False)


@router.message(F.successful_payment)
async def process_successful_payment_handler(message: Message, db: UniversalDatabase, state: FSMContext):
    """Обработка успешного платежа"""
    try:
        user_id = message.from_user.id
        payment = message.successful_payment

        # Создаем сервис платежей
        payment_service = create_payment_service(
            provider_token=YOOKASSA_PROVIDER_TOKEN,
            currency=YOOKASSA_CURRENCY,
            provider_data=YOOKASSA_PROVIDER_DATA,
            db=db
        )

        # Обрабатываем успешный платеж
        success = await payment_service.process_successful_payment(payment, user_id)

        if success:
            # Очищаем состояние
            await state.clear()

            # Уведомляем пользователя об успешной активации
            amount_display = payment_service.format_amount_for_display(payment.total_amount)
            await message.answer(
                f"✅ <b>Подписка успешно активирована!</b>\n\n"
                f"💰 Оплачено: {amount_display}\n"
                f"📅 Срок действия: 30 дней\n\n"
                f"Теперь у вас есть безлимитный доступ к поиску каналов!\n\n"
                f"Используйте /profile для просмотра деталей подписки.",
                parse_mode="HTML"
            )

            logger.info(f"Подписка успешно активирована для пользователя {user_id}, "
                       f"сумма: {payment.total_amount} копеек")
        else:
            await message.answer(
                "❌ <b>Ошибка при активации подписки</b>\n\n"
                "Платеж прошел, но возникла ошибка при активации подписки. "
                "Обратитесь к администратору.",
                parse_mode="HTML"
            )
            logger.error(f"Не удалось активировать подписку для пользователя {user_id} "
                        f"после успешного платежа")

    except Exception as e:
        logger.error(f"Ошибка при обработке успешного платежа для пользователя {message.from_user.id}: {e}")
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Обратитесь к администратору для решения проблемы.",
            parse_mode="HTML"
        )


# Обработчик неуспешных платежей (когда пользователь в состоянии ожидания платежа)
@router.message(PaymentStates.waiting_payment)
async def process_unsuccessful_payment(message: Message, state: FSMContext):
    """Обработка неуспешного платежа или отмены"""
    await state.clear()
    await message.answer(
        "❌ <b>Платеж не был завершен</b>\n\n"
        "Если у вас возникли проблемы с оплатой, попробуйте еще раз "
        "или обратитесь к администратору.\n\n"
        "Используйте /subscribe для повторной попытки.",
        parse_mode="HTML"
    )
    logger.info(f"Платеж не завершен для пользователя {message.from_user.id}")
