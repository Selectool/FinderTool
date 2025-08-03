"""
Система разрешений и декораторы
"""
from functools import wraps
from typing import List, Optional
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .auth import verify_token, check_permission
from .models import TokenData

# Схема безопасности
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    """Получить текущего пользователя из токена"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = verify_token(credentials.credentials)
    if token_data is None:
        raise credentials_exception
    
    return token_data


async def get_current_active_user(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Получить текущего активного пользователя"""
    # Здесь можно добавить дополнительные проверки активности пользователя
    return current_user


def require_permissions(permissions: List[str]):
    """Декоратор для проверки разрешений"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Получаем пользователя из зависимостей
            current_user = None
            for key, value in kwargs.items():
                if isinstance(value, TokenData):
                    current_user = value
                    break
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Проверяем разрешения
            for permission in permissions:
                if not check_permission(current_user.role, permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: {permission}"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class PermissionChecker:
    """Класс для проверки разрешений как зависимость FastAPI"""

    def __init__(self, required_permissions: List[str]):
        self.required_permissions = required_permissions

    def __call__(self, current_user: TokenData = Depends(get_current_active_user)) -> TokenData:
        for permission in self.required_permissions:
            if not check_permission(current_user.role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}"
                )
        return current_user


# Предопределенные проверки разрешений
RequireUserView = PermissionChecker(["users.view"])
RequireUserEdit = PermissionChecker(["users.edit"])
RequireBroadcastCreate = PermissionChecker(["broadcasts.create"])
RequireBroadcastSend = PermissionChecker(["broadcasts.send"])
RequireStatisticsView = PermissionChecker(["statistics.view"])
RequireTemplateManage = PermissionChecker(["templates.create", "templates.edit"])
RequireAuditView = PermissionChecker(["audit.view"])
RequireSuperAdmin = PermissionChecker(["*"])


def log_admin_action(action: str, resource_type: str):
    """Декоратор для логирования действий админа"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Получаем пользователя и request из аргументов
            current_user = None
            request = None
            db = None
            
            for key, value in kwargs.items():
                if isinstance(value, TokenData):
                    current_user = value
                elif isinstance(value, Request):
                    request = value
                elif hasattr(value, 'log_admin_action'):  # UniversalDatabase instance
                    db = value
            
            # Выполняем функцию
            result = await func(*args, **kwargs)
            
            # Логируем действие
            if current_user and db:
                try:
                    details = {
                        "function": func.__name__,
                        "args": str(args),
                        "result": "success"
                    }
                    
                    ip_address = None
                    user_agent = None
                    
                    if request:
                        ip_address = request.client.host if request.client else None
                        user_agent = request.headers.get("user-agent")
                    
                    await db.log_admin_action(
                        admin_user_id=current_user.user_id,
                        action=action,
                        resource_type=resource_type,
                        details=details,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                except Exception as e:
                    # Не прерываем выполнение из-за ошибки логирования
                    print(f"Ошибка логирования: {e}")
            
            return result
        return wrapper
    return decorator


# Список всех доступных разрешений
ALL_PERMISSIONS = [
    {"name": "users.view", "description": "Просмотр пользователей", "category": "users"},
    {"name": "users.edit", "description": "Редактирование пользователей", "category": "users"},
    {"name": "users.manage_subscription", "description": "Управление подписками", "category": "users"},
    {"name": "broadcasts.create", "description": "Создание рассылок", "category": "broadcasts"},
    {"name": "broadcasts.send", "description": "Отправка рассылок", "category": "broadcasts"},
    {"name": "broadcasts.view", "description": "Просмотр рассылок", "category": "broadcasts"},
    {"name": "templates.create", "description": "Создание шаблонов", "category": "templates"},
    {"name": "templates.edit", "description": "Редактирование шаблонов", "category": "templates"},
    {"name": "templates.delete", "description": "Удаление шаблонов", "category": "templates"},
    {"name": "statistics.view", "description": "Просмотр статистики", "category": "statistics"},
    {"name": "audit.view", "description": "Просмотр логов", "category": "audit"},
    {"name": "system.logs", "description": "Системные логи", "category": "system"},
]
