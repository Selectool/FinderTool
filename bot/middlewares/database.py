"""
Middleware для передачи объекта базы данных в обработчики
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.universal_database import UniversalDatabase


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для передачи объекта базы данных"""

    def __init__(self, db: UniversalDatabase):
        self.db = db
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Добавляем объект базы данных в данные
        data["db"] = self.db
        
        # Вызываем следующий обработчик
        return await handler(event, data)
