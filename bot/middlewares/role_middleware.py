"""
Middleware для проверки ролей пользователей
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from database.universal_database import UniversalDatabase
from bot.utils.roles import TelegramUserPermissions, log_role_action

logger = logging.getLogger(__name__)


class RoleMiddleware(BaseMiddleware):
    """Middleware для проверки и установки ролей пользователей"""
    
    def __init__(self):
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем пользователя из события
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        # Получаем базу данных из данных
        db: UniversalDatabase = data.get("db")
        if not db:
            logger.warning("Database not found in middleware data")
            return await handler(event, data)
        
        try:
            # Получаем роль пользователя из базы данных
            user_role = await db.get_user_role(user.id)
            
            # Добавляем информацию о роли в данные
            data["user_role"] = user_role
            data["user_permissions"] = TelegramUserPermissions
            
            # Логируем доступ
            log_role_action(
                user.id, 
                "MIDDLEWARE_ACCESS", 
                f"Role: {user_role}, Handler: {handler.__name__ if hasattr(handler, '__name__') else 'unknown'}"
            )
            
        except Exception as e:
            logger.error(f"Error in RoleMiddleware for user {user.id}: {e}")
            # В случае ошибки устанавливаем роль по умолчанию
            data["user_role"] = TelegramUserPermissions.get_user_role(user.id)
            data["user_permissions"] = TelegramUserPermissions
        
        # Вызываем следующий обработчик
        return await handler(event, data)


class AdminOnlyMiddleware(BaseMiddleware):
    """Middleware для ограничения доступа только администраторам"""
    
    def __init__(self, error_message: str = "❌ Функция доступна только администраторам"):
        super().__init__()
        self.error_message = error_message
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем пользователя из события
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        # Получаем роль пользователя
        user_role = data.get("user_role")
        if not user_role:
            # Если роль не установлена, получаем её
            db: UniversalDatabase = data.get("db")
            if db:
                user_role = await db.get_user_role(user.id)
            else:
                user_role = TelegramUserPermissions.get_user_role(user.id)
        
        # Проверяем права администратора
        if not TelegramUserPermissions.is_admin(user.id, user_role):
            # Отправляем сообщение об ошибке
            if isinstance(event, Message):
                await event.answer(self.error_message)
            elif isinstance(event, CallbackQuery):
                await event.answer(self.error_message, show_alert=True)
            
            log_role_action(user.id, "ADMIN_ACCESS_DENIED", f"Handler: {handler.__name__ if hasattr(handler, '__name__') else 'unknown'}")
            return
        
        log_role_action(user.id, "ADMIN_ACCESS_GRANTED", f"Handler: {handler.__name__ if hasattr(handler, '__name__') else 'unknown'}")
        return await handler(event, data)


class UnlimitedAccessMiddleware(BaseMiddleware):
    """Middleware для ограничения доступа пользователям с безлимитным доступом"""
    
    def __init__(self, error_message: str = "❌ Функция доступна только пользователям с безлимитным доступом"):
        super().__init__()
        self.error_message = error_message
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем пользователя из события
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        # Получаем роль пользователя
        user_role = data.get("user_role")
        if not user_role:
            # Если роль не установлена, получаем её
            db: UniversalDatabase = data.get("db")
            if db:
                user_role = await db.get_user_role(user.id)
            else:
                user_role = TelegramUserPermissions.get_user_role(user.id)
        
        # Проверяем безлимитный доступ
        if not TelegramUserPermissions.has_unlimited_access(user.id, user_role):
            # Отправляем сообщение об ошибке
            if isinstance(event, Message):
                await event.answer(self.error_message)
            elif isinstance(event, CallbackQuery):
                await event.answer(self.error_message, show_alert=True)
            
            log_role_action(user.id, "UNLIMITED_ACCESS_DENIED", f"Handler: {handler.__name__ if hasattr(handler, '__name__') else 'unknown'}")
            return
        
        log_role_action(user.id, "UNLIMITED_ACCESS_GRANTED", f"Handler: {handler.__name__ if hasattr(handler, '__name__') else 'unknown'}")
        return await handler(event, data)


class DeveloperOnlyMiddleware(BaseMiddleware):
    """Middleware для ограничения доступа только разработчикам"""
    
    def __init__(self, error_message: str = "❌ Функция доступна только разработчикам"):
        super().__init__()
        self.error_message = error_message
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем пользователя из события
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        # Получаем роль пользователя
        user_role = data.get("user_role")
        if not user_role:
            # Если роль не установлена, получаем её
            db: UniversalDatabase = data.get("db")
            if db:
                user_role = await db.get_user_role(user.id)
            else:
                user_role = TelegramUserPermissions.get_user_role(user.id)
        
        # Проверяем права разработчика
        if not TelegramUserPermissions.is_developer(user.id, user_role):
            # Отправляем сообщение об ошибке
            if isinstance(event, Message):
                await event.answer(self.error_message)
            elif isinstance(event, CallbackQuery):
                await event.answer(self.error_message, show_alert=True)
            
            log_role_action(user.id, "DEVELOPER_ACCESS_DENIED", f"Handler: {handler.__name__ if hasattr(handler, '__name__') else 'unknown'}")
            return
        
        log_role_action(user.id, "DEVELOPER_ACCESS_GRANTED", f"Handler: {handler.__name__ if hasattr(handler, '__name__') else 'unknown'}")
        return await handler(event, data)


# Вспомогательные функции для использования в обработчиках
def get_user_role(data: Dict[str, Any]) -> str:
    """Получить роль пользователя из данных middleware"""
    return data.get("user_role", "user")


def get_user_permissions(data: Dict[str, Any]) -> TelegramUserPermissions:
    """Получить объект разрешений пользователя из данных middleware"""
    return data.get("user_permissions", TelegramUserPermissions)


def has_role_access(data: Dict[str, Any], required_role: str) -> bool:
    """Проверить, имеет ли пользователь доступ к определенной роли"""
    from bot.utils.roles import RoleHierarchy
    
    user_role = get_user_role(data)
    user_level = RoleHierarchy.get_role_level(user_role)
    required_level = RoleHierarchy.get_role_level(required_role)
    
    return user_level >= required_level
