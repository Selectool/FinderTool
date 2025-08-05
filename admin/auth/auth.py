"""
JWT аутентификация с production-ready управлением токенами
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import json
import logging

from ..config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_REFRESH_TOKEN_EXPIRE_DAYS
from .models import TokenData
from .jwt_manager import jwt_manager

logger = logging.getLogger(__name__)

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверить пароль"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Получить хеш пароля"""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Создать access токен (DEPRECATED - используйте jwt_manager.create_token_pair)"""
    logger.warning("⚠️  Используется устаревший метод create_access_token. Рекомендуется jwt_manager.create_token_pair")

    # Для обратной совместимости
    user_id = data.get("sub", 0)
    username = data.get("username", "unknown")
    role = data.get("role", "admin")

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        user_id = 0

    token_pair = jwt_manager.create_token_pair(user_id, username, role)
    return token_pair["access_token"]


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Создать refresh токен (DEPRECATED - используйте jwt_manager.create_token_pair)"""
    logger.warning("⚠️  Используется устаревый метод create_refresh_token. Рекомендуется jwt_manager.create_token_pair")

    # Для обратной совместимости
    user_id = data.get("sub", 0)
    username = data.get("username", "unknown")
    role = data.get("role", "admin")

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        user_id = 0

    token_pair = jwt_manager.create_token_pair(user_id, username, role)
    return token_pair["refresh_token"]


def create_token_pair(user_id: int, username: str, role: str = "admin") -> Dict[str, Any]:
    """Создать пару токенов (access + refresh) - РЕКОМЕНДУЕМЫЙ МЕТОД"""
    return jwt_manager.create_token_pair(user_id, username, role)


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """Проверить токен с использованием production-ready менеджера"""
    try:
        logger.info(f"🔍 Декодирование токена типа {token_type}: {token[:20]}...")

        # Используем новый JWT менеджер
        token_info = jwt_manager.verify_token(token, token_type)

        if not token_info:
            logger.warning(f"⚠️ Токен не прошел валидацию в JWT менеджере")
            return None

        logger.info(f"🔍 Данные из токена: user_id={token_info.user_id}, username={token_info.username}, role={token_info.role}")

        token_data = TokenData(
            user_id=token_info.user_id,
            username=token_info.username,
            role=token_info.role
        )

        logger.info(f"✅ Токен успешно проверен для {token_info.username}")
        return token_data

    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при проверке токена: {e}")
        return None


def revoke_token(token: str) -> bool:
    """Отозвать токен"""
    return jwt_manager.revoke_token(token)


def revoke_user_sessions(user_id: int) -> int:
    """Отозвать все сессии пользователя"""
    return jwt_manager.revoke_user_sessions(user_id)


def get_jwt_stats() -> Dict[str, Any]:
    """Получить статистику JWT"""
    return jwt_manager.get_stats()


def create_tokens(user: Dict[str, Any]) -> Dict[str, Any]:
    """Создать пару токенов для пользователя"""
    access_token_expires = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    token_data = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user["role"]
    }
    
    access_token = create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )
    
    refresh_token = create_refresh_token(data=token_data)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


async def authenticate_user(db, username: str, password: str) -> Optional[Dict[str, Any]]:
    """Аутентифицировать пользователя"""
    user = await db.get_admin_user_by_username(username)
    if not user:
        return None
    
    if not verify_password(password, user["password_hash"]):
        return None
    
    # Обновляем время последнего входа
    await db.update_admin_user_login(user["id"])
    
    return user


def require_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    # Здесь можно добавить логику проверки прав администратора
    # Пока что возвращаем True для всех пользователей
    return True


def check_permission(user_role: str, required_permission: str) -> bool:
    """Проверить права пользователя"""
    # Базовая система прав
    role_permissions = {
        "super_admin": ["*"],  # Все права
        "admin": [
            "users.view", "users.edit", "users.delete",
            "broadcasts.view", "broadcasts.create", "broadcasts.edit", "broadcasts.delete",
            "statistics.view", "audit.view"
        ],
        "moderator": [
            "users.view", "broadcasts.view", "broadcasts.create",
            "statistics.view"
        ]
    }

    user_permissions = role_permissions.get(user_role, [])

    # Супер админ имеет все права
    if "*" in user_permissions:
        return True

    # Проверяем конкретное право
    return required_permission in user_permissions
