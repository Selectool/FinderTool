"""
Обработчики подписки и платежей
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command

from database.models import Database
from bot.keyboards.inline import get_subscription_keyboard, get_back_keyboard
from config import TEXTS, SUBSCRIPTION_PRICE, BOT_TOKEN
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, db: Database):
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
async def callback_subscribe(callback: CallbackQuery, db: Database):
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
async def callback_pay_subscription(callback: CallbackQuery):
    """Callback оплаты подписки"""
    # Пока что заглушка для оплаты
    # В будущем здесь будет интеграция с платежной системой
    
    await callback.message.edit_text(
        "💳 <b>Оплата подписки</b>\n\n"
        "🚧 Функция оплаты находится в разработке.\n\n"
        "Для активации подписки обратитесь к администратору:\n"
        "@admin_username\n\n"
        "Стоимость: 500₽/месяц",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


# Заглушки для будущей интеграции с платежами
# Эти функции будут реализованы при подключении платежной системы

async def create_invoice(user_id: int, amount: int, description: str):
    """Создать инвойс для оплаты (заглушка)"""
    # Здесь будет логика создания инвойса через Telegram Payments
    # или другую платежную систему
    pass


async def process_successful_payment(user_id: int, payment_data: dict, db: Database):
    """Обработать успешную оплату (заглушка)"""
    # Здесь будет логика активации подписки после успешной оплаты
    await db.subscribe_user(user_id, months=1)
    logger.info(f"Подписка активирована для пользователя {user_id}")


# Пример обработчиков для Telegram Payments (закомментированы)
"""
@router.callback_query(F.data == "pay_subscription")
async def callback_pay_subscription(callback: CallbackQuery):
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Подписка Channel Finder Bot",
        description="Безлимитные запросы на поиск похожих каналов",
        payload="subscription_1_month",
        provider_token="PROVIDER_TOKEN",  # Токен платежного провайдера
        currency="RUB",
        prices=[LabeledPrice(label="Подписка на месяц", amount=SUBSCRIPTION_PRICE * 100)]
    )
    await callback.answer()


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment_handler(message: Message, db: Database):
    payment = message.successful_payment
    user_id = message.from_user.id
    
    if payment.invoice_payload == "subscription_1_month":
        await db.subscribe_user(user_id, months=1)
        await message.answer(
            "✅ <b>Подписка успешно активирована!</b>\n\n"
            "Теперь у вас есть безлимитный доступ к поиску каналов на месяц.",
            parse_mode="HTML"
        )
        logger.info(f"Подписка активирована для пользователя {user_id}")
"""
