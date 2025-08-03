"""
JWT аутентификация
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import json

from ..config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_REFRESH_TOKEN_EXPIRE_DAYS
from .models import TokenData

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверить пароль"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Получить хеш пароля"""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Создать access токен"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Создать refresh токен"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """Проверить токен"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # Проверяем тип токена
        if payload.get("type") != token_type:
            return None
        
        user_id: int = payload.get("sub")
        username: str = payload.get("username")
        role: str = payload.get("role")
        
        if user_id is None:
            return None
        
        return TokenData(user_id=user_id, username=username, role=role)
    
    except JWTError:
        return None


def create_tokens(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Создать пару токенов"""
    access_token_expires = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    access_token = create_access_token(
        data={"sub": user_data["id"], "username": user_data["username"], "role": user_data["role"]},
        expires_delta=access_token_expires
    )
    
    refresh_token = create_refresh_token(
        data={"sub": user_data["id"], "username": user_data["username"], "role": user_data["role"]}
    )
    
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


def get_user_permissions(role: str) -> list:
    """Получить разрешения пользователя по роли"""
    permissions_map = {
        "super_admin": ["*"],  # Все разрешения
        "admin": [
            "users.view", "users.edit", "users.manage_subscription",
            "broadcasts.create", "broadcasts.send", "broadcasts.view",
            "templates.create", "templates.edit", "templates.delete",
            "statistics.view", "audit.view"
        ],
        "developer": [
            "users.view", "statistics.view", "broadcasts.create", "broadcasts.view",
            "templates.create", "templates.edit", "audit.view", "system.logs"
        ],
        "moderator": [
            "users.view", "statistics.view", "broadcasts.view"
        ]
    }
    
    return permissions_map.get(role, [])


def check_permission(user_role: str, required_permission: str) -> bool:
    """Проверить разрешение пользователя"""
    user_permissions = get_user_permissions(user_role)

    # Супер админ имеет все права
    if "*" in user_permissions:
        return True

    return required_permission in user_permissions


def require_admin(permission: str = None):
    """
    Декоратор для проверки прав администратора

    Args:
        permission: Требуемое разрешение (опционально)
    """
    from functools import wraps
    from fastapi import Depends, HTTPException, status
    from fastapi.security import HTTPBearer

    security = HTTPBearer()

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Получаем токен из зависимостей
            token = kwargs.get('token') or (args[0] if args else None)

            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Токен не предоставлен"
                )

            # Проверяем токен
            token_data = verify_token(token.credentials if hasattr(token, 'credentials') else str(token))
            if not token_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительный токен"
                )

            # Проверяем разрешения если указаны
            if permission and not check_permission(token_data.role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Недостаточно прав для {permission}"
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator
