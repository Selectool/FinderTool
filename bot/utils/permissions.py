"""
Production-ready модуль для управления правами доступа
"""
import logging
from functools import wraps
from typing import Callable, Any
from aiogram.types import Message, CallbackQuery

from config import DEVELOPER_IDS

logger = logging.getLogger(__name__)


class UserPermissions:
    """Класс для управления правами пользователей"""
    
    @staticmethod
    def is_developer(user_id: int) -> bool:
        """Проверить, является ли пользователь разработчиком"""
        return user_id in DEVELOPER_IDS
    
    @staticmethod
    def is_admin(user_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        # Можно расширить логику для админов
        return UserPermissions.is_developer(user_id)
    
    @staticmethod
    def has_unlimited_access(user_id: int) -> bool:
        """Проверить, есть ли у пользователя безлимитный доступ"""
        return UserPermissions.is_developer(user_id)


def developer_only(func: Callable) -> Callable:
    """Декоратор для команд, доступных только разработчикам"""
    @wraps(func)
    async def wrapper(message_or_callback: Any, *args, **kwargs):
        # Определяем тип объекта и получаем user_id
        if isinstance(message_or_callback, Message):
            user_id = message_or_callback.from_user.id
            send_method = message_or_callback.answer
        elif isinstance(message_or_callback, CallbackQuery):
            user_id = message_or_callback.from_user.id
            send_method = message_or_callback.message.answer
        else:
            logger.error(f"Неподдерживаемый тип объекта: {type(message_or_callback)}")
            return
        
        if not UserPermissions.is_developer(user_id):
            await send_method("❌ Команда доступна только разработчикам")
            logger.warning(f"Пользователь {user_id} попытался использовать команду разработчика")
            return
        
        logger.info(f"🔧 Разработчик {user_id} использует команду: {func.__name__}")
        return await func(message_or_callback, *args, **kwargs)
    
    return wrapper


def unlimited_access_check(user_id: int) -> bool:
    """Проверка безлимитного доступа с логированием"""
    if UserPermissions.has_unlimited_access(user_id):
        logger.info(f"🔧 Разработчик {user_id} получил безлимитный доступ")
        return True
    return False
