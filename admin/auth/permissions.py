"""
Система разрешений и декораторы
Production-Ready Universal Authentication
"""
from functools import wraps
from typing import List, Optional
from fastapi import HTTPException, status, Depends, Request, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from .auth import verify_token, check_permission
from .models import TokenData

logger = logging.getLogger(__name__)

# Схема безопасности
security = HTTPBearer(auto_error=False)  # auto_error=False для поддержки cookies


async def get_current_user_universal(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    access_token: Optional[str] = Cookie(None)
) -> TokenData:
    """
    Production-Ready Universal Authentication
    Поддерживает токены из Authorization header и cookies
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = None
    auth_method = None

    # Приоритет 1: Authorization header
    if credentials and credentials.credentials:
        token = credentials.credentials
        auth_method = "Authorization header"
        logger.debug(f"🔐 Токен из Authorization header: {token[:20]}...")

    # Приоритет 2: Cookie
    elif access_token:
        token = access_token
        auth_method = "Cookie"
        logger.debug(f"🔐 Токен из cookie: {token[:20]}...")

    if not token:
        logger.warning("❌ Токен не найден ни в заголовках, ни в cookies")
        raise credentials_exception

    logger.info(f"🔐 Проверка токена ({auth_method}): {token[:20]}...")

    token_data = verify_token(token)
    if token_data is None:
        logger.warning(f"❌ Токен недействителен ({auth_method})")
        raise credentials_exception

    logger.info(f"✅ Токен валиден ({auth_method}). Пользователь: {token_data.username}, роль: {token_data.role}")
    return token_data


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    """
    Получить текущего пользователя из токена (только Authorization header)
    Deprecated: используйте get_current_user_universal для production
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    logger.info(f"🔐 Проверка токена: {credentials.credentials[:20]}...")

    token_data = verify_token(credentials.credentials)
    if token_data is None:
        logger.warning("❌ Токен недействителен")
        raise credentials_exception

    logger.info(f"✅ Токен валиден. Пользователь: {token_data.username}, роль: {token_data.role}")
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
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"🔒 Проверка прав для пользователя {current_user.username} (роль: {current_user.role})")
        logger.info(f"🔒 Требуемые права: {self.required_permissions}")

        for permission in self.required_permissions:
            has_permission = check_permission(current_user.role, permission)
            logger.info(f"🔒 Право '{permission}': {'✅ ЕСТЬ' if has_permission else '❌ НЕТ'}")

            if not has_permission:
                logger.warning(f"❌ Доступ запрещен для {current_user.username}: нет права {permission}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}"
                )

        logger.info(f"✅ Все права проверены для {current_user.username}")
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
                    import json
                    details_dict = {
                        "function": func.__name__,
                        "args": str(args)[:500],  # Ограничиваем длину для безопасности
                        "result": "success"
                    }

                    # Сериализуем детали в JSON строку
                    details_json = json.dumps(details_dict, ensure_ascii=False)

                    ip_address = None
                    user_agent = None

                    if request:
                        ip_address = request.client.host if request.client else None
                        user_agent = request.headers.get("user-agent")

                    await db.log_admin_action(
                        admin_user_id=current_user.user_id,
                        action=action,
                        resource_type=resource_type,
                        details=details_json,  # Передаем JSON строку
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
