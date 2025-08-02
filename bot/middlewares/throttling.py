"""
Throttling Middleware для Telegram бота
Ограничение частоты запросов от пользователей
"""

import asyncio
import logging
import time
from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User, Message, CallbackQuery

logger = logging.getLogger(__name__)

class ThrottlingMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов"""
    
    def __init__(
        self, 
        rate_limit: float = 1.0,  # Секунд между запросами
        key_prefix: str = "throttle"
    ):
        self.rate_limit = rate_limit
        self.key_prefix = key_prefix
        self.storage: Dict[int, float] = {}  # user_id -> last_request_time
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Основная логика throttling"""
        
        # Получаем пользователя
        user: Optional[User] = data.get("event_from_user")
        
        if not user:
            # Если пользователь не найден, пропускаем throttling
            return await handler(event, data)
        
        # Проверяем throttling
        if await self._check_throttling(user.id, event):
            # Если throttling сработал, не выполняем handler
            return
        
        # Обновляем время последнего запроса
        self.storage[user.id] = time.time()
        
        # Продолжаем выполнение
        return await handler(event, data)
    
    async def _check_throttling(self, user_id: int, event: TelegramObject) -> bool:
        """
        Проверка throttling для пользователя
        Returns True если запрос заблокирован
        """
        current_time = time.time()
        last_request_time = self.storage.get(user_id, 0)
        
        # Проверяем, прошло ли достаточно времени
        if current_time - last_request_time < self.rate_limit:
            # Throttling сработал
            await self._handle_throttling(user_id, event)
            return True
        
        return False
    
    async def _handle_throttling(self, user_id: int, event: TelegramObject):
        """Обработка заблокированного запроса"""
        
        logger.debug(f"🚫 Throttling для пользователя {user_id}")
        
        # Отправляем предупреждение только для сообщений
        if isinstance(event, Message):
            try:
                await event.answer(
                    "⏱ Пожалуйста, подождите немного перед следующим запросом.",
                    show_alert=False
                )
            except Exception as e:
                logger.debug(f"Не удалось отправить throttling сообщение: {e}")
        
        elif isinstance(event, CallbackQuery):
            try:
                await event.answer(
                    "⏱ Слишком частые запросы. Подождите немного.",
                    show_alert=True
                )
            except Exception as e:
                logger.debug(f"Не удалось отправить throttling callback: {e}")

class AdvancedThrottlingMiddleware(BaseMiddleware):
    """Продвинутый throttling с разными лимитами для разных действий"""
    
    def __init__(self):
        self.storage: Dict[str, float] = {}  # key -> last_request_time
        self.limits = {
            "message": 1.0,      # 1 секунда между сообщениями
            "callback": 0.5,     # 0.5 секунды между callback
            "search": 3.0,       # 3 секунды между поисками
            "payment": 10.0,     # 10 секунд между платежами
        }
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Основная логика продвинутого throttling"""
        
        user: Optional[User] = data.get("event_from_user")
        
        if not user:
            return await handler(event, data)
        
        # Определяем тип действия
        action_type = self._get_action_type(event, data)
        
        # Создаем ключ для throttling
        throttle_key = f"{user.id}:{action_type}"
        
        # Проверяем throttling
        if await self._check_advanced_throttling(throttle_key, action_type, event):
            return
        
        # Обновляем время последнего запроса
        self.storage[throttle_key] = time.time()
        
        return await handler(event, data)
    
    def _get_action_type(self, event: TelegramObject, data: Dict[str, Any]) -> str:
        """Определение типа действия для throttling"""
        
        if isinstance(event, CallbackQuery):
            callback_data = event.data or ""
            
            if "search" in callback_data:
                return "search"
            elif "pay" in callback_data or "payment" in callback_data:
                return "payment"
            else:
                return "callback"
        
        elif isinstance(event, Message):
            text = event.text or ""
            
            if any(keyword in text.lower() for keyword in ["найди", "поиск", "search"]):
                return "search"
            else:
                return "message"
        
        return "message"
    
    async def _check_advanced_throttling(
        self, 
        throttle_key: str, 
        action_type: str, 
        event: TelegramObject
    ) -> bool:
        """Проверка продвинутого throttling"""
        
        current_time = time.time()
        last_request_time = self.storage.get(throttle_key, 0)
        rate_limit = self.limits.get(action_type, 1.0)
        
        if current_time - last_request_time < rate_limit:
            await self._handle_advanced_throttling(action_type, event)
            return True
        
        return False
    
    async def _handle_advanced_throttling(self, action_type: str, event: TelegramObject):
        """Обработка продвинутого throttling"""
        
        messages = {
            "search": "🔍 Подождите перед следующим поиском (3 сек)",
            "payment": "💳 Подождите перед следующей операцией с платежом (10 сек)",
            "callback": "⏱ Слишком быстро! Подождите немного",
            "message": "📝 Пожалуйста, пишите не так часто"
        }
        
        message = messages.get(action_type, "⏱ Подождите немного")
        
        if isinstance(event, Message):
            try:
                await event.answer(message)
            except Exception:
                pass
        elif isinstance(event, CallbackQuery):
            try:
                await event.answer(message, show_alert=True)
            except Exception:
                pass
