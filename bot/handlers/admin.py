"""
Админ обработчики
"""
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models import Database
from bot.keyboards.inline import get_admin_keyboard, get_back_keyboard, get_broadcast_confirm_keyboard
from config import ADMIN_USER_ID
import logging

logger = logging.getLogger(__name__)
router = Router()


class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirming_broadcast = State()


def is_admin(user_id: int) -> bool:
    """Проверка на админа"""
    return user_id == ADMIN_USER_ID


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ панель"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    await message.answer(
        "👨‍💼 <b>Админ панель</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )


@router.callback_query(F.data == "admin_stats")
async def callback_admin_stats(callback: CallbackQuery, db: Database):
    """Статистика бота"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа")
        return
    
    stats = await db.get_stats()
    
    stats_text = f"""
📊 <b>Статистика бота</b>

👥 Всего пользователей: {stats['total_users']}
💎 Активных подписчиков: {stats['active_subscribers']}
🔍 Запросов сегодня: {stats['requests_today']}

📈 Конверсия в подписку: {(stats['active_subscribers'] / max(stats['total_users'], 1) * 100):.1f}%
    """
    
    await callback.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def callback_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    """Начать рассылку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа")
        return
    
    await callback.message.edit_text(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Отправьте сообщение, которое хотите разослать всем пользователям.\n\n"
        "Поддерживается HTML разметка.",
        parse_mode="HTML"
    )
    
    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.answer()


@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Обработка сообщения для рассылки"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    # Сохраняем сообщение в состоянии
    await state.update_data(broadcast_message=message.html_text)
    
    preview_text = f"""
📢 <b>Предварительный просмотр рассылки:</b>

{message.html_text}

───────────────────

Отправить это сообщение всем пользователям?
    """
    
    await message.answer(
        preview_text,
        parse_mode="HTML",
        reply_markup=get_broadcast_confirm_keyboard()
    )
    
    await state.set_state(BroadcastStates.confirming_broadcast)


@router.callback_query(F.data == "confirm_broadcast", BroadcastStates.confirming_broadcast)
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, db: Database):
    """Подтверждение рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа")
        await state.clear()
        return
    
    data = await state.get_data()
    broadcast_message = data.get('broadcast_message')
    
    if not broadcast_message:
        await callback.answer("❌ Сообщение не найдено")
        await state.clear()
        return
    
    await callback.message.edit_text(
        "📤 <b>Начинаю рассылку...</b>\n\n"
        "Это может занять некоторое время.",
        parse_mode="HTML"
    )
    
    # Получаем всех пользователей
    users = await db.get_all_users()
    
    sent_count = 0
    failed_count = 0
    
    # Рассылаем сообщения
    for user in users:
        try:
            from bot.utils.error_handler import safe_send_message

            success = await safe_send_message(
                bot=callback.bot,
                user_id=user['user_id'],
                text=broadcast_message,
                db=db,
                parse_mode="HTML"
            )

            if success:
                sent_count += 1
            else:
                failed_count += 1

            # Небольшая задержка чтобы не превысить лимиты API
            await asyncio.sleep(0.05)

        except Exception as e:
            failed_count += 1
            logger.error(f"Ошибка отправки пользователю {user['user_id']}: {e}")
    
    # Отчет о рассылке
    report_text = f"""
✅ <b>Рассылка завершена!</b>

📤 Отправлено: {sent_count}
❌ Не доставлено: {failed_count}
👥 Всего пользователей: {len(users)}

📊 Успешность: {(sent_count / max(len(users), 1) * 100):.1f}%
    """
    
    await callback.message.edit_text(
        report_text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel_broadcast", BroadcastStates.confirming_broadcast)
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки"""
    await callback.message.edit_text(
        "❌ <b>Рассылка отменена</b>",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "admin_users")
async def callback_admin_users(callback: CallbackQuery, db: Database):
    """Управление пользователями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа")
        return
    
    # Пока что простая заглушка
    await callback.message.edit_text(
        "👥 <b>Управление пользователями</b>\n\n"
        "🚧 Функция в разработке\n\n"
        "Планируемые возможности:\n"
        "• Просмотр списка пользователей\n"
        "• Активация/деактивация подписок\n"
        "• Блокировка пользователей\n"
        "• Детальная статистика",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()
