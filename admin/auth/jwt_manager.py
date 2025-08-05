"""
Production-ready JWT Token Manager
Обеспечивает стабильное управление JWT токенами с поддержкой:
- Фиксированных ключей безопасности
- Token blacklisting
- Session management
- Key rotation (для будущих версий)
- Proper error handling
"""

import time
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Set, List
from jose import JWTError, jwt
import logging
from dataclasses import dataclass
from threading import Lock

from ..config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_REFRESH_TOKEN_EXPIRE_DAYS, ENVIRONMENT

logger = logging.getLogger(__name__)

@dataclass
class TokenInfo:
    """Информация о токене"""
    user_id: int
    username: str
    role: str
    token_type: str
    jti: str  # JWT ID для отзыва
    issued_at: datetime
    expires_at: datetime
    last_activity: datetime

class ProductionJWTManager:
    """Production-ready менеджер JWT токенов"""
    
    def __init__(self):
        self.secret_key = JWT_SECRET_KEY
        self.algorithm = JWT_ALGORITHM
        self.access_token_expire_minutes = JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = JWT_REFRESH_TOKEN_EXPIRE_DAYS
        
        # Thread-safe хранилища
        self._lock = Lock()
        self._active_sessions: Dict[str, TokenInfo] = {}  # jti -> TokenInfo
        self._user_sessions: Dict[int, Set[str]] = {}     # user_id -> set of jti
        self._blacklisted_tokens: Set[str] = set()        # Отозванные токены
        
        # Статистика
        self._stats = {
            'tokens_created': 0,
            'tokens_verified': 0,
            'tokens_revoked': 0,
            'failed_verifications': 0
        }
        
        logger.info(f"🔐 JWT Manager инициализирован для окружения: {ENVIRONMENT}")
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Валидация конфигурации JWT"""
        if len(self.secret_key) < 32:
            if ENVIRONMENT == "production":
                raise ValueError("JWT_SECRET_KEY должен быть минимум 32 символа для production!")
            logger.warning("⚠️  JWT_SECRET_KEY слишком короткий для production")
        
        # Проверяем, что ключ не содержит небезопасные паттерны
        unsafe_patterns = ["dev-", "test-", "auto-generated", "change-in-production"]
        if ENVIRONMENT == "production":
            for pattern in unsafe_patterns:
                if pattern in self.secret_key.lower():
                    raise ValueError(f"Небезопасный паттерн '{pattern}' в JWT_SECRET_KEY для production!")
        
        logger.info("✅ JWT конфигурация валидна")
    
    def create_token_pair(self, user_id: int, username: str, role: str = "admin") -> Dict[str, Any]:
        """Создание пары access + refresh токенов"""
        with self._lock:
            try:
                # Генерируем уникальные JTI для каждого токена
                access_jti = secrets.token_urlsafe(16)
                refresh_jti = secrets.token_urlsafe(16)
                
                now = datetime.utcnow()
                
                # Access token
                access_expire = now + timedelta(minutes=self.access_token_expire_minutes)
                access_payload = {
                    "sub": str(user_id),
                    "username": username,
                    "role": role,
                    "type": "access",
                    "jti": access_jti,
                    "iat": now,
                    "exp": access_expire,
                    "iss": "telegram-bot-admin",
                    "aud": "admin-panel"
                }
                
                # Refresh token
                refresh_expire = now + timedelta(days=self.refresh_token_expire_days)
                refresh_payload = {
                    "sub": str(user_id),
                    "username": username,
                    "role": role,
                    "type": "refresh",
                    "jti": refresh_jti,
                    "iat": now,
                    "exp": refresh_expire,
                    "iss": "telegram-bot-admin",
                    "aud": "admin-panel"
                }
                
                # Создаем токены
                access_token = jwt.encode(access_payload, self.secret_key, algorithm=self.algorithm)
                refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm=self.algorithm)
                
                # Сохраняем информацию о сессиях
                access_info = TokenInfo(
                    user_id=user_id,
                    username=username,
                    role=role,
                    token_type="access",
                    jti=access_jti,
                    issued_at=now,
                    expires_at=access_expire,
                    last_activity=now
                )
                
                refresh_info = TokenInfo(
                    user_id=user_id,
                    username=username,
                    role=role,
                    token_type="refresh",
                    jti=refresh_jti,
                    issued_at=now,
                    expires_at=refresh_expire,
                    last_activity=now
                )
                
                self._active_sessions[access_jti] = access_info
                self._active_sessions[refresh_jti] = refresh_info
                
                # Добавляем к пользовательским сессиям
                if user_id not in self._user_sessions:
                    self._user_sessions[user_id] = set()
                self._user_sessions[user_id].add(access_jti)
                self._user_sessions[user_id].add(refresh_jti)
                
                self._stats['tokens_created'] += 2
                
                logger.info(f"🔐 Создана пара токенов для пользователя {username} (ID: {user_id})")
                
                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "expires_in": self.access_token_expire_minutes * 60,
                    "refresh_expires_in": self.refresh_token_expire_days * 24 * 60 * 60
                }
                
            except Exception as e:
                logger.error(f"❌ Ошибка создания токенов: {e}")
                raise
    
    def verify_token(self, token: str, expected_type: str = "access") -> Optional[TokenInfo]:
        """Проверка и валидация токена"""
        with self._lock:
            try:
                # Проверяем blacklist
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                if token_hash in self._blacklisted_tokens:
                    logger.warning("⚠️  Попытка использования отозванного токена")
                    self._stats['failed_verifications'] += 1
                    return None
                
                # Декодируем токен
                payload = jwt.decode(
                    token,
                    self.secret_key,
                    algorithms=[self.algorithm],
                    audience="admin-panel",
                    issuer="telegram-bot-admin"
                )
                
                # Проверяем тип токена
                if payload.get("type") != expected_type:
                    logger.warning(f"⚠️  Неверный тип токена: ожидался {expected_type}, получен {payload.get('type')}")
                    self._stats['failed_verifications'] += 1
                    return None
                
                jti = payload.get("jti")
                if not jti or jti not in self._active_sessions:
                    logger.warning("⚠️  Токен не найден в активных сессиях")
                    self._stats['failed_verifications'] += 1
                    return None
                
                # Получаем информацию о сессии
                token_info = self._active_sessions[jti]
                
                # Обновляем время последней активности
                token_info.last_activity = datetime.utcnow()
                
                self._stats['tokens_verified'] += 1
                
                logger.debug(f"✅ Токен успешно проверен для {token_info.username}")
                return token_info
                
            except jwt.ExpiredSignatureError:
                logger.warning("⚠️  JWT токен истек")
                self._stats['failed_verifications'] += 1
                return None
            except jwt.JWTError as e:
                logger.warning(f"⚠️  Неверный JWT токен: {e}")
                self._stats['failed_verifications'] += 1
                return None
            except Exception as e:
                logger.error(f"❌ Ошибка проверки JWT токена: {e}")
                self._stats['failed_verifications'] += 1
                return None
    
    def revoke_token(self, token: str) -> bool:
        """Отзыв токена"""
        with self._lock:
            try:
                # Добавляем в blacklist
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                self._blacklisted_tokens.add(token_hash)
                
                # Пытаемся получить JTI из токена
                try:
                    payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm], options={"verify_exp": False})
                    jti = payload.get("jti")
                    user_id = int(payload.get("sub", 0))
                    
                    if jti and jti in self._active_sessions:
                        del self._active_sessions[jti]
                        
                        # Удаляем из пользовательских сессий
                        if user_id in self._user_sessions:
                            self._user_sessions[user_id].discard(jti)
                            if not self._user_sessions[user_id]:
                                del self._user_sessions[user_id]
                    
                except:
                    pass  # Игнорируем ошибки декодирования для отзыва
                
                self._stats['tokens_revoked'] += 1
                logger.info("🔐 Токен успешно отозван")
                return True
                
            except Exception as e:
                logger.error(f"❌ Ошибка отзыва токена: {e}")
                return False
    
    def revoke_user_sessions(self, user_id: int) -> int:
        """Отзыв всех сессий пользователя"""
        with self._lock:
            try:
                if user_id not in self._user_sessions:
                    return 0
                
                user_jtis = self._user_sessions[user_id].copy()
                revoked_count = 0
                
                for jti in user_jtis:
                    if jti in self._active_sessions:
                        del self._active_sessions[jti]
                        revoked_count += 1
                
                del self._user_sessions[user_id]
                self._stats['tokens_revoked'] += revoked_count
                
                logger.info(f"🔐 Отозвано {revoked_count} сессий для пользователя {user_id}")
                return revoked_count
                
            except Exception as e:
                logger.error(f"❌ Ошибка отзыва сессий пользователя: {e}")
                return 0
    
    def cleanup_expired_sessions(self) -> int:
        """Очистка истекших сессий"""
        with self._lock:
            try:
                now = datetime.utcnow()
                expired_jtis = []
                
                for jti, token_info in self._active_sessions.items():
                    if token_info.expires_at < now:
                        expired_jtis.append(jti)
                
                # Удаляем истекшие сессии
                for jti in expired_jtis:
                    token_info = self._active_sessions[jti]
                    del self._active_sessions[jti]
                    
                    # Удаляем из пользовательских сессий
                    user_id = token_info.user_id
                    if user_id in self._user_sessions:
                        self._user_sessions[user_id].discard(jti)
                        if not self._user_sessions[user_id]:
                            del self._user_sessions[user_id]
                
                if expired_jtis:
                    logger.info(f"🧹 Очищено {len(expired_jtis)} истекших сессий")
                
                return len(expired_jtis)
                
            except Exception as e:
                logger.error(f"❌ Ошибка очистки истекших сессий: {e}")
                return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики"""
        with self._lock:
            return {
                **self._stats,
                'active_sessions': len(self._active_sessions),
                'active_users': len(self._user_sessions),
                'blacklisted_tokens': len(self._blacklisted_tokens)
            }

    def clear_all_sessions(self) -> int:
        """Очистить все активные сессии (для смены ключей безопасности)"""
        with self._lock:
            try:
                session_count = len(self._active_sessions)
                self._active_sessions.clear()
                self._user_sessions.clear()
                self._blacklisted_tokens.clear()

                logger.info(f"🧹 Очищено {session_count} активных сессий")
                return session_count

            except Exception as e:
                logger.error(f"❌ Ошибка очистки сессий: {e}")
                return 0

# Глобальный экземпляр менеджера
jwt_manager = ProductionJWTManager()
