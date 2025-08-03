"""
Authentication Middleware для Telegram бота
Проверка авторизации пользователей и ограничение доступа
"""

import logging
from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from database.universal_database import UniversalDatabase

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseMiddleware):
    """Middleware для аутентификации пользователей"""
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Основная логика middleware"""
        
        # Получаем пользователя из события
        user: Optional[User] = data.get("event_from_user")
        
        if not user:
            # Если пользователь не найден, пропускаем
            return await handler(event, data)
        
        try:
            # Если база данных доступна, проверяем/создаем пользователя
            if self.db:
                # Проверяем существование пользователя в базе
                db_user = await self.db.get_user(user.id)
                
                if not db_user:
                    # Создаем нового пользователя
                    await self.db.add_user(
                        user_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name
                    )
                    logger.info(f"👤 Новый пользователь зарегистрирован: {user.id} (@{user.username})")
                else:
                    # Обновляем информацию о пользователе
                    await self.db.update_user_info(
                        user_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name
                    )
                
                # Добавляем информацию о пользователе в данные
                data["db_user"] = db_user or await self.db.get_user(user.id)
            
            # Логируем активность пользователя
            logger.debug(f"🔐 Пользователь {user.id} (@{user.username}) прошел аутентификацию")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в AuthMiddleware для пользователя {user.id}: {e}")
            # Не блокируем выполнение при ошибках в middleware
        
        # Продолжаем выполнение
        return await handler(event, data)

class AdminAuthMiddleware(BaseMiddleware):
    """Middleware для проверки прав администратора"""
    
    def __init__(self, admin_user_ids: list = None):
        self.admin_user_ids = admin_user_ids or []
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Проверка прав администратора"""
        
        user: Optional[User] = data.get("event_from_user")
        
        if not user:
            logger.warning("⚠️ Попытка доступа к админ-функции без пользователя")
            return
        
        if user.id not in self.admin_user_ids:
            logger.warning(f"⚠️ Пользователь {user.id} (@{user.username}) попытался получить доступ к админ-функции")
            return
        
        logger.info(f"🔑 Администратор {user.id} (@{user.username}) получил доступ")
        return await handler(event, data)
