"""
Базовые обработчики команд
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from database.models import Database
from bot.keyboards.inline import get_main_menu, get_back_keyboard
from config import TEXTS, SUBSCRIPTION_PRICE, FREE_REQUESTS_LIMIT, DEVELOPER_IDS

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, db: Database):
    """Обработчик команды /start"""
    user = message.from_user
    
    # Создаем или обновляем пользователя в БД
    await db.create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    await message.answer(
        TEXTS["start"].format(price=SUBSCRIPTION_PRICE),
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    await message.answer(
        TEXTS["help"],
        parse_mode="HTML"
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message, db: Database):
    """Обработчик команды /profile"""
    user_data = await db.get_user(message.from_user.id)
    
    if not user_data:
        await message.answer("❌ Пользователь не найден. Используйте /start")
        return
    
    user_id = message.from_user.id
    from bot.utils.roles import TelegramUserPermissions

    user_role = await db.get_user_role(user_id)
    role_display = TelegramUserPermissions.get_role_display_name(user_role)
    has_unlimited = TelegramUserPermissions.has_unlimited_access(user_id, user_role)
    is_subscribed = await db.check_subscription(user_id)
    requests_left = max(0, FREE_REQUESTS_LIMIT - user_data['requests_used'])

    profile_text = f"""
👤 <b>Ваш профиль</b>

🆔 ID: {user_data['user_id']}
👤 Имя: {user_data['first_name'] or 'Не указано'}
📅 Регистрация: {user_data['created_at'][:10]}
🎭 Роль: {role_display}

📊 <b>Статистика:</b>
🔍 Запросов использовано: {user_data['requests_used']}
"""

    if has_unlimited:
        profile_text += f"🔧 <b>Статус: {role_display.upper()}</b>\n💎 Безлимитный доступ ко всем функциям"
    elif is_subscribed:
        profile_text += f"💎 Статус: Подписчик до {user_data['subscription_end'][:10]}"
    else:
        profile_text += f"🆓 Бесплатных запросов осталось: {requests_left}"
    
    await message.answer(
        profile_text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )


@router.callback_query(F.data == "profile")
async def callback_profile(callback: CallbackQuery, db: Database):
    """Callback для профиля"""
    user_data = await db.get_user(callback.from_user.id)
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден")
        return
    
    user_id = callback.from_user.id
    from bot.utils.roles import TelegramUserPermissions

    user_role = await db.get_user_role(user_id)
    role_display = TelegramUserPermissions.get_role_display_name(user_role)
    has_unlimited = TelegramUserPermissions.has_unlimited_access(user_id, user_role)
    is_subscribed = await db.check_subscription(user_id)
    requests_left = max(0, FREE_REQUESTS_LIMIT - user_data['requests_used'])

    profile_text = f"""
👤 <b>Ваш профиль</b>

🆔 ID: {user_data['user_id']}
👤 Имя: {user_data['first_name'] or 'Не указано'}
📅 Регистрация: {user_data['created_at'][:10]}
🎭 Роль: {role_display}

📊 <b>Статистика:</b>
🔍 Запросов использовано: {user_data['requests_used']}
"""

    if has_unlimited:
        profile_text += f"🔧 <b>Статус: {role_display.upper()}</b>\n💎 Безлимитный доступ ко всем функциям"
    elif is_subscribed:
        profile_text += f"💎 Статус: Подписчик до {user_data['subscription_end'][:10]}"
    else:
        profile_text += f"🆓 Бесплатных запросов осталось: {requests_left}"
    
    await callback.message.edit_text(
        profile_text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Callback для помощи"""
    await callback.message.edit_text(
        TEXTS["help"],
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def callback_back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        TEXTS["start"].format(price=SUBSCRIPTION_PRICE),
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )
    await callback.answer()
