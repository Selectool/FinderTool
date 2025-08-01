"""
Reply клавиатуры для бота FinderTool
Production-ready реализация с поддержкой ролей
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from typing import Optional


def get_main_menu_keyboard(user_role: str = "user") -> ReplyKeyboardMarkup:
    """
    Основная Reply клавиатура с адаптацией под роль пользователя
    
    Args:
        user_role: Роль пользователя (user, admin, senior_admin, developer)
    
    Returns:
        ReplyKeyboardMarkup: Настроенная клавиатура
    """
    builder = ReplyKeyboardBuilder()
    
    # Основные функции для всех пользователей
    builder.row(
        KeyboardButton(text="📊 Мой профиль"),
        KeyboardButton(text="💎 Подписка")
    )
    
    builder.row(
        KeyboardButton(text="📖 Помощь"),
        KeyboardButton(text="🏠 Главное меню")
    )
    
    # Админские функции для пользователей с соответствующими ролями
    if user_role in ["admin", "senior_admin", "developer"]:
        builder.row(
            KeyboardButton(text="⚙️ Админ панель")
        )
    
    # Дополнительные функции для разработчиков
    if user_role == "developer":
        builder.row(
            KeyboardButton(text="🔧 Dev панель")
        )
    
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Отправьте ссылку на канал для поиска..."
    )


def get_compact_menu_keyboard(user_role: str = "user") -> ReplyKeyboardMarkup:
    """
    Компактная Reply клавиатура для мобильных устройств
    
    Args:
        user_role: Роль пользователя
    
    Returns:
        ReplyKeyboardMarkup: Компактная клавиатура
    """
    builder = ReplyKeyboardBuilder()
    
    # Основные функции в одну строку
    builder.row(
        KeyboardButton(text="📊 Профиль"),
        KeyboardButton(text="💎 Подписка"),
        KeyboardButton(text="📖 Помощь")
    )
    
    # Админские функции
    if user_role in ["admin", "senior_admin", "developer"]:
        builder.row(
            KeyboardButton(text="⚙️ Админ"),
            KeyboardButton(text="🏠 Меню")
        )
    else:
        builder.row(
            KeyboardButton(text="🏠 Главное меню")
        )
    
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Ссылка на канал..."
    )


def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """
    Алиас для get_admin_menu_keyboard для обратной совместимости

    Returns:
        ReplyKeyboardMarkup: Админская клавиатура
    """
    return get_admin_menu_keyboard()


def get_admin_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Специальная Reply клавиатура для админов

    Returns:
        ReplyKeyboardMarkup: Админская клавиатура
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="💳 Платежи")
    )

    builder.row(
        KeyboardButton(text="📢 Рассылка"),
        KeyboardButton(text="👥 Пользователи")
    )

    builder.row(
        KeyboardButton(text="🏠 Главное меню")
    )

    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите действие..."
    )


def get_subscription_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Reply клавиатура для управления подпиской
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура подписки
    """
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="💎 Оформить подписку"),
        KeyboardButton(text="📊 Статус подписки")
    )
    
    builder.row(
        KeyboardButton(text="🏠 Главное меню")
    )
    
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Управление подпиской..."
    )


def remove_keyboard() -> ReplyKeyboardMarkup:
    """
    Убрать Reply клавиатуру
    
    Returns:
        ReplyKeyboardMarkup: Пустая клавиатура для удаления
    """
    from aiogram.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove()


def get_role_based_keyboard(user_role: str, context: str = "main") -> ReplyKeyboardMarkup:
    """
    Получить клавиатуру в зависимости от роли и контекста
    
    Args:
        user_role: Роль пользователя
        context: Контекст использования (main, admin, subscription)
    
    Returns:
        ReplyKeyboardMarkup: Соответствующая клавиатура
    """
    if context == "admin" and user_role in ["admin", "senior_admin", "developer"]:
        return get_admin_menu_keyboard()
    elif context == "subscription":
        return get_subscription_menu_keyboard()
    elif context == "compact":
        return get_compact_menu_keyboard(user_role)
    else:
        return get_main_menu_keyboard(user_role)


# Константы для текстов кнопок
class ReplyButtons:
    """Константы для текстов Reply кнопок"""

    # Основные функции
    MAIN_MENU = "🏠 Главное меню"
    PROFILE = "📊 Мой профиль"
    SUBSCRIPTION = "💎 Подписка"
    HELP = "📖 Помощь"
    SEARCH = "🔍 Поиск каналов"

    # Админские функции
    ADMIN_PANEL = "⚙️ Админ панель"
    DEV_PANEL = "🔧 Dev панель"
    STATISTICS = "📊 Статистика"
    PAYMENTS = "💳 Платежи"
    BROADCAST = "📢 Рассылка"
    USERS = "👥 Пользователи"

    # Подписка
    SUBSCRIBE = "💎 Оформить подписку"
    SUBSCRIPTION_STATUS = "📊 Статус подписки"

    # Компактные версии
    PROFILE_SHORT = "📊 Профиль"
    SUBSCRIPTION_SHORT = "💎 Подписка"
    HELP_SHORT = "📖 Помощь"
    ADMIN_SHORT = "⚙️ Админ"
    MENU_SHORT = "🏠 Меню"


def is_reply_button(text: str) -> bool:
    """
    Проверить, является ли текст кнопкой Reply клавиатуры
    
    Args:
        text: Текст для проверки
    
    Returns:
        bool: True если это кнопка Reply клавиатуры
    """
    reply_buttons = [
        ReplyButtons.MAIN_MENU,
        ReplyButtons.PROFILE,
        ReplyButtons.SUBSCRIPTION,
        ReplyButtons.HELP,
        ReplyButtons.SEARCH,
        ReplyButtons.ADMIN_PANEL,
        ReplyButtons.DEV_PANEL,
        ReplyButtons.STATISTICS,
        ReplyButtons.PAYMENTS,
        ReplyButtons.BROADCAST,
        ReplyButtons.USERS,
        ReplyButtons.SUBSCRIBE,
        ReplyButtons.SUBSCRIPTION_STATUS,
        ReplyButtons.PROFILE_SHORT,
        ReplyButtons.SUBSCRIPTION_SHORT,
        ReplyButtons.HELP_SHORT,
        ReplyButtons.ADMIN_SHORT,
        ReplyButtons.MENU_SHORT
    ]
    
    return text in reply_buttons


def get_keyboard_for_user(user_id: int, user_role: str = "user", 
                         context: str = "main", compact: bool = False) -> ReplyKeyboardMarkup:
    """
    Production-ready функция получения клавиатуры для конкретного пользователя
    
    Args:
        user_id: ID пользователя
        user_role: Роль пользователя
        context: Контекст использования
        compact: Использовать компактную версию
    
    Returns:
        ReplyKeyboardMarkup: Персонализированная клавиатура
    """
    if compact:
        return get_compact_menu_keyboard(user_role)
    else:
        return get_role_based_keyboard(user_role, context)
