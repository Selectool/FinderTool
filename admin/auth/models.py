"""
Модели аутентификации
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserLogin(BaseModel):
    """Модель для входа в систему"""
    username: str
    password: str


class UserCreate(BaseModel):
    """Модель для создания пользователя"""
    username: str
    email: EmailStr
    password: str
    role: str = "moderator"


class UserResponse(BaseModel):
    """Модель ответа с информацией о пользователе"""
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class Token(BaseModel):
    """Модель токена"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Данные токена"""
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None


class RefreshToken(BaseModel):
    """Модель для обновления токена"""
    refresh_token: str


class PasswordChange(BaseModel):
    """Модель для смены пароля"""
    current_password: str
    new_password: str


class Role(BaseModel):
    """Модель роли"""
    id: int
    name: str
    display_name: str
    permissions: List[str]
    description: Optional[str] = None


class Permission(BaseModel):
    """Модель разрешения"""
    name: str
    description: str
    category: str
