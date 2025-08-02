"""
Production-Ready Security для Админ-панели
JWT Authentication, Rate Limiting, CSRF Protection
Senior Developer уровень безопасности
"""

import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from functools import wraps

import jwt
from fastapi import HTTPException, Request, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import SECRET_KEY, JWT_SECRET_KEY, ADMIN_USER_IDS

logger = logging.getLogger(__name__)

# Rate Limiter для защиты от брутфорса
limiter = Limiter(key_func=get_remote_address)

# Security схема для JWT
security = HTTPBearer()

class ProductionSecurityManager:
    """Production-ready менеджер безопасности"""
    
    def __init__(self):
        self.jwt_secret = JWT_SECRET_KEY or SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire = 3600  # 1 час
        self.refresh_token_expire = 2592000  # 30 дней
        
        # Хранилище активных сессий (в production использовать Redis)
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Blacklist отозванных токенов
        self.token_blacklist: set = set()
        
        # Счетчики неудачных попыток входа
        self.failed_attempts: Dict[str, List[float]] = {}
        
        # CSRF токены
        self.csrf_tokens: Dict[str, Dict[str, Any]] = {}
    
    def generate_jwt_token(self, user_id: int, token_type: str = "access") -> str:
        """Генерация JWT токена"""
        try:
            now = datetime.utcnow()
            
            if token_type == "access":
                expire = now + timedelta(seconds=self.access_token_expire)
            elif token_type == "refresh":
                expire = now + timedelta(seconds=self.refresh_token_expire)
            else:
                raise ValueError(f"Неизвестный тип токена: {token_type}")
            
            payload = {
                "user_id": user_id,
                "type": token_type,
                "iat": now,
                "exp": expire,
                "jti": secrets.token_urlsafe(16),  # JWT ID для отзыва
                "iss": "telegram-bot-admin",  # Issuer
                "aud": "admin-panel"  # Audience
            }
            
            token = jwt.encode(payload, self.jwt_secret, algorithm=self.algorithm)
            
            # Сохраняем в активные сессии
            self._store_active_session(user_id, token, payload)
            
            logger.info(f"🔐 Создан {token_type} токен для пользователя {user_id}")
            return token
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации JWT токена: {e}")
            raise
    
    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Проверка JWT токена"""
        try:
            # Проверяем blacklist
            if token in self.token_blacklist:
                logger.warning("⚠️ Попытка использования отозванного токена")
                return None
            
            # Декодируем токен
            payload = jwt.decode(
                token, 
                self.jwt_secret, 
                algorithms=[self.algorithm],
                audience="admin-panel",
                issuer="telegram-bot-admin"
            )
            
            user_id = payload.get("user_id")
            jti = payload.get("jti")
            
            # Проверяем активную сессию
            if not self._verify_active_session(user_id, jti):
                logger.warning(f"⚠️ Сессия не найдена или истекла: {user_id}")
                return None
            
            # Проверяем права администратора
            if not self._verify_admin_permissions(user_id):
                logger.warning(f"⚠️ Недостаточно прав: {user_id}")
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("⚠️ JWT токен истек")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"⚠️ Неверный JWT токен: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки JWT токена: {e}")
            return None
    
    def _store_active_session(self, user_id: int, token: str, payload: Dict[str, Any]):
        """Сохранение активной сессии"""
        jti = payload.get("jti")
        if user_id not in self.active_sessions:
            self.active_sessions[user_id] = {}
        
        self.active_sessions[user_id][jti] = {
            "token": token,
            "created_at": time.time(),
            "expires_at": payload.get("exp").timestamp() if payload.get("exp") else 0,
            "type": payload.get("type"),
            "last_activity": time.time()
        }
    
    def _verify_active_session(self, user_id: int, jti: str) -> bool:
        """Проверка активной сессии"""
        if user_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[user_id].get(jti)
        if not session:
            return False
        
        # Проверяем срок действия
        if session["expires_at"] < time.time():
            self._remove_session(user_id, jti)
            return False
        
        # Обновляем последнюю активность
        session["last_activity"] = time.time()
        return True
    
    def _verify_admin_permissions(self, user_id: int) -> bool:
        """Проверка прав администратора"""
        admin_ids = [int(id.strip()) for id in ADMIN_USER_IDS.split(",") if id.strip()]
        return user_id in admin_ids
    
    def _remove_session(self, user_id: int, jti: str):
        """Удаление сессии"""
        if user_id in self.active_sessions and jti in self.active_sessions[user_id]:
            del self.active_sessions[user_id][jti]
            if not self.active_sessions[user_id]:
                del self.active_sessions[user_id]
    
    def revoke_token(self, token: str) -> bool:
        """Отзыв токена"""
        try:
            # Добавляем в blacklist
            self.token_blacklist.add(token)
            
            # Декодируем для получения информации
            payload = jwt.decode(
                token, 
                self.jwt_secret, 
                algorithms=[self.algorithm],
                options={"verify_exp": False}  # Игнорируем истечение для отзыва
            )
            
            user_id = payload.get("user_id")
            jti = payload.get("jti")
            
            # Удаляем из активных сессий
            self._remove_session(user_id, jti)
            
            logger.info(f"🔐 Токен отозван для пользователя {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отзыва токена: {e}")
            return False
    
    def revoke_all_user_tokens(self, user_id: int) -> int:
        """Отзыв всех токенов пользователя"""
        count = 0
        
        if user_id in self.active_sessions:
            sessions = self.active_sessions[user_id].copy()
            
            for jti, session in sessions.items():
                token = session["token"]
                self.token_blacklist.add(token)
                count += 1
            
            del self.active_sessions[user_id]
        
        logger.info(f"🔐 Отозвано {count} токенов для пользователя {user_id}")
        return count
    
    def generate_csrf_token(self, user_id: int) -> str:
        """Генерация CSRF токена"""
        csrf_token = secrets.token_urlsafe(32)
        
        self.csrf_tokens[csrf_token] = {
            "user_id": user_id,
            "created_at": time.time(),
            "expires_at": time.time() + 3600  # 1 час
        }
        
        return csrf_token
    
    def verify_csrf_token(self, csrf_token: str, user_id: int) -> bool:
        """Проверка CSRF токена"""
        if csrf_token not in self.csrf_tokens:
            return False
        
        token_data = self.csrf_tokens[csrf_token]
        
        # Проверяем срок действия
        if token_data["expires_at"] < time.time():
            del self.csrf_tokens[csrf_token]
            return False
        
        # Проверяем пользователя
        if token_data["user_id"] != user_id:
            return False
        
        return True
    
    def check_rate_limit(self, identifier: str, max_attempts: int = 5, window: int = 300) -> bool:
        """Проверка rate limiting"""
        current_time = time.time()
        
        if identifier not in self.failed_attempts:
            self.failed_attempts[identifier] = []
        
        # Очищаем старые попытки
        self.failed_attempts[identifier] = [
            attempt for attempt in self.failed_attempts[identifier]
            if current_time - attempt < window
        ]
        
        # Проверяем лимит
        if len(self.failed_attempts[identifier]) >= max_attempts:
            logger.warning(f"⚠️ Rate limit превышен для {identifier}")
            return False
        
        return True
    
    def record_failed_attempt(self, identifier: str):
        """Запись неудачной попытки"""
        if identifier not in self.failed_attempts:
            self.failed_attempts[identifier] = []
        
        self.failed_attempts[identifier].append(time.time())
    
    def cleanup_expired_data(self):
        """Очистка истекших данных"""
        current_time = time.time()
        
        # Очистка истекших сессий
        for user_id in list(self.active_sessions.keys()):
            sessions = self.active_sessions[user_id]
            expired_sessions = [
                jti for jti, session in sessions.items()
                if session["expires_at"] < current_time
            ]
            
            for jti in expired_sessions:
                del sessions[jti]
            
            if not sessions:
                del self.active_sessions[user_id]
        
        # Очистка истекших CSRF токенов
        expired_csrf = [
            token for token, data in self.csrf_tokens.items()
            if data["expires_at"] < current_time
        ]
        
        for token in expired_csrf:
            del self.csrf_tokens[token]
        
        # Очистка старых неудачных попыток
        for identifier in list(self.failed_attempts.keys()):
            self.failed_attempts[identifier] = [
                attempt for attempt in self.failed_attempts[identifier]
                if current_time - attempt < 3600  # Храним 1 час
            ]
            
            if not self.failed_attempts[identifier]:
                del self.failed_attempts[identifier]
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Получение статистики безопасности"""
        return {
            "active_sessions": sum(len(sessions) for sessions in self.active_sessions.values()),
            "blacklisted_tokens": len(self.token_blacklist),
            "csrf_tokens": len(self.csrf_tokens),
            "failed_attempts_ips": len(self.failed_attempts),
            "total_failed_attempts": sum(len(attempts) for attempts in self.failed_attempts.values())
        }

# Глобальный экземпляр менеджера безопасности
security_manager = ProductionSecurityManager()

# Dependency для проверки JWT токена
async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Dependency для получения текущего администратора"""
    token = credentials.credentials
    payload = security_manager.verify_jwt_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен доступа",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload

# Dependency для проверки CSRF токена
async def verify_csrf(request: Request, current_admin: Dict = Depends(get_current_admin)) -> bool:
    """Dependency для проверки CSRF токена"""
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        csrf_token = request.headers.get("X-CSRF-Token")
        
        if not csrf_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF токен отсутствует"
            )
        
        user_id = current_admin.get("user_id")
        
        if not security_manager.verify_csrf_token(csrf_token, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недействительный CSRF токен"
            )
    
    return True

# Rate limiting decorator
def rate_limit(max_calls: int = 10, window: int = 60):
    """Декоратор для rate limiting"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            client_ip = get_remote_address(request)
            
            if not security_manager.check_rate_limit(client_ip, max_calls, window):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Слишком много запросов. Попробуйте позже."
                )
            
            try:
                return await func(request, *args, **kwargs)
            except HTTPException as e:
                if e.status_code in [401, 403]:
                    security_manager.record_failed_attempt(client_ip)
                raise
        
        return wrapper
    return decorator

# Экспорт основных компонентов
__all__ = [
    'security_manager', 
    'get_current_admin', 
    'verify_csrf', 
    'rate_limit',
    'limiter'
]
