"""
Inline клавиатуры бота
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu() -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Мой профиль", callback_data="profile"),
        InlineKeyboardButton(text="💎 Подписка", callback_data="subscribe")
    )
    builder.row(
        InlineKeyboardButton(text="📖 Помощь", callback_data="help")
    )
    return builder.as_markup()


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подписки"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Оплатить подписку", callback_data="pay_subscription")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")
    )
    return builder.as_markup()


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Админ клавиатура"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
        InlineKeyboardButton(text="🎭 Роли", callback_data="roles_menu")
    )
    return builder.as_markup()


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка назад"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")
    )
    return builder.as_markup()


def get_audience_selection_keyboard() -> InlineKeyboardMarkup:
    """Выбор аудитории для рассылки"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Все пользователи", callback_data="audience_all")
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Активные пользователи", callback_data="audience_active")
    )
    builder.row(
        InlineKeyboardButton(text="💎 Подписчики", callback_data="audience_subscribers")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")
    )
    return builder.as_markup()


def get_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение рассылки"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_send_now"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")
    )
    return builder.as_markup()
