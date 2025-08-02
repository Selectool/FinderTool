"""
Production-ready security middleware для защиты бота
"""
import asyncio
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery

from config import (
    IS_PRODUCTION, RATE_LIMIT_ENABLED, MAX_REQUESTS_PER_MINUTE, 
    MAX_REQUESTS_PER_HOUR, REQUEST_TIMEOUT
)

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Rate limiting middleware для защиты от спама"""
    
    def __init__(self):
        self.user_requests: Dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_REQUESTS_PER_HOUR))
        self.blocked_users: Dict[int, datetime] = {}
        self.cleanup_interval = 300  # 5 минут
        self.last_cleanup = time.time()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not RATE_LIMIT_ENABLED:
            return await handler(event, data)
        
        # Получаем user_id из события
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None
        
        if not user_id:
            return await handler(event, data)
        
        # Проверяем блокировку пользователя
        if user_id in self.blocked_users:
            if datetime.now() < self.blocked_users[user_id]:
                logger.warning(f"Заблокированный пользователь {user_id} пытается отправить запрос")
                return  # Игнорируем запрос
            else:
                # Разблокируем пользователя
                del self.blocked_users[user_id]
        
        # Проверяем rate limit
        now = time.time()
        user_requests = self.user_requests[user_id]
        
        # Удаляем старые запросы (старше часа)
        while user_requests and user_requests[0] < now - 3600:
            user_requests.popleft()
        
        # Проверяем лимит за минуту
        recent_requests = sum(1 for req_time in user_requests if req_time > now - 60)
        if recent_requests >= MAX_REQUESTS_PER_MINUTE:
            logger.warning(f"Пользователь {user_id} превысил лимит запросов в минуту: {recent_requests}")
            await self._block_user(user_id, minutes=5)
            return
        
        # Проверяем лимит за час
        if len(user_requests) >= MAX_REQUESTS_PER_HOUR:
            logger.warning(f"Пользователь {user_id} превысил лимит запросов в час: {len(user_requests)}")
            await self._block_user(user_id, minutes=60)
            return
        
        # Добавляем текущий запрос
        user_requests.append(now)
        
        # Периодическая очистка
        if now - self.last_cleanup > self.cleanup_interval:
            await self._cleanup()
            self.last_cleanup = now
        
        return await handler(event, data)
    
    async def _block_user(self, user_id: int, minutes: int):
        """Заблокировать пользователя на указанное время"""
        block_until = datetime.now() + timedelta(minutes=minutes)
        self.blocked_users[user_id] = block_until
        logger.info(f"Пользователь {user_id} заблокирован до {block_until}")
    
    async def _cleanup(self):
        """Очистка старых данных"""
        now = time.time()
        
        # Очищаем старые запросы
        for user_id in list(self.user_requests.keys()):
            user_requests = self.user_requests[user_id]
            while user_requests and user_requests[0] < now - 3600:
                user_requests.popleft()
            
            # Удаляем пустые очереди
            if not user_requests:
                del self.user_requests[user_id]
        
        # Очищаем истекшие блокировки
        current_time = datetime.now()
        expired_blocks = [
            user_id for user_id, block_time in self.blocked_users.items()
            if current_time >= block_time
        ]
        for user_id in expired_blocks:
            del self.blocked_users[user_id]
        
        logger.debug(f"Очистка завершена. Активных пользователей: {len(self.user_requests)}, заблокированных: {len(self.blocked_users)}")


class SecurityMiddleware(BaseMiddleware):
    """Общий security middleware"""
    
    def __init__(self):
        self.suspicious_activity: Dict[int, int] = defaultdict(int)
        self.banned_users = set()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not IS_PRODUCTION:
            return await handler(event, data)
        
        # Получаем информацию о пользователе
        user_id = None
        username = None
        
        if isinstance(event, (Message, CallbackQuery)):
            if event.from_user:
                user_id = event.from_user.id
                username = event.from_user.username
        
        if not user_id:
            return await handler(event, data)
        
        # Проверяем забанненых пользователей
        if user_id in self.banned_users:
            logger.warning(f"Забанненый пользователь {user_id} (@{username}) пытается использовать бота")
            return
        
        # Проверяем подозрительную активность
        if await self._is_suspicious_activity(event, user_id):
            self.suspicious_activity[user_id] += 1
            
            if self.suspicious_activity[user_id] >= 5:
                logger.error(f"Пользователь {user_id} (@{username}) заблокирован за подозрительную активность")
                self.banned_users.add(user_id)
                return
        
        # Добавляем security контекст в данные
        data['security_context'] = {
            'user_id': user_id,
            'username': username,
            'is_production': IS_PRODUCTION,
            'suspicious_score': self.suspicious_activity.get(user_id, 0)
        }
        
        return await handler(event, data)
    
    async def _is_suspicious_activity(self, event: TelegramObject, user_id: int) -> bool:
        """Проверка на подозрительную активность"""
        if isinstance(event, Message):
            message = event
            
            # Проверяем на спам-паттерны
            if message.text:
                text = message.text.lower()
                
                # Подозрительные паттерны
                spam_patterns = [
                    'http://', 'https://', 'www.',  # Ссылки от неизвестных пользователей
                    'bitcoin', 'crypto', 'earn money',  # Крипто-спам
                    'free money', 'click here', 'limited time',  # Классический спам
                ]
                
                spam_score = sum(1 for pattern in spam_patterns if pattern in text)
                if spam_score >= 2:
                    logger.warning(f"Подозрительное сообщение от {user_id}: {text[:100]}...")
                    return True
                
                # Проверяем на повторяющиеся сообщения
                if len(text) > 100 and text.count(text[:20]) > 3:
                    logger.warning(f"Повторяющееся сообщение от {user_id}")
                    return True
        
        return False


class TimeoutMiddleware(BaseMiddleware):
    """Middleware для контроля таймаутов запросов"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            # Устанавливаем таймаут для обработки запроса
            return await asyncio.wait_for(
                handler(event, data),
                timeout=REQUEST_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"Таймаут обработки запроса: {type(event).__name__}")
            
            # Отправляем сообщение об ошибке пользователю
            if isinstance(event, Message):
                try:
                    await event.answer("⏱️ Запрос обрабатывается слишком долго. Попробуйте позже.")
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения о таймауте: {e}")
            
            return None
        except Exception as e:
            logger.error(f"Ошибка в TimeoutMiddleware: {e}")
            raise


class ProductionMonitoringMiddleware(BaseMiddleware):
    """Middleware для мониторинга в production"""
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.start_time = time.time()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not IS_PRODUCTION:
            return await handler(event, data)
        
        self.request_count += 1
        start_time = time.time()
        
        try:
            result = await handler(event, data)
            
            # Логируем медленные запросы
            processing_time = time.time() - start_time
            if processing_time > 5.0:  # Медленнее 5 секунд
                logger.warning(f"Медленный запрос: {type(event).__name__} - {processing_time:.2f}с")
            
            return result
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Ошибка обработки {type(event).__name__}: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику мониторинга"""
        uptime = time.time() - self.start_time
        return {
            'uptime_seconds': uptime,
            'total_requests': self.request_count,
            'total_errors': self.error_count,
            'error_rate': self.error_count / max(self.request_count, 1),
            'requests_per_second': self.request_count / max(uptime, 1)
        }
