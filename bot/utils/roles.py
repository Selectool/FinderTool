"""
Система ролей для Telegram пользователей
"""
import logging
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class TelegramUserRole(str, Enum):
    """Роли пользователей Telegram бота"""
    USER = "user"                    # Обычный пользователь
    ADMIN = "admin"                  # Администратор
    SENIOR_ADMIN = "senior_admin"    # Старший администратор
    DEVELOPER = "developer"          # Разработчик


class RoleHierarchy:
    """Иерархия ролей и их уровни доступа"""
    
    # Уровни ролей (чем выше число, тем больше прав)
    ROLE_LEVELS = {
        TelegramUserRole.USER: 0,
        TelegramUserRole.ADMIN: 1,
        TelegramUserRole.SENIOR_ADMIN: 2,
        TelegramUserRole.DEVELOPER: 3
    }
    
    # Роли с безлимитным доступом
    UNLIMITED_ACCESS_ROLES = {
        TelegramUserRole.ADMIN,
        TelegramUserRole.SENIOR_ADMIN,
        TelegramUserRole.DEVELOPER
    }
    
    # Роли с административными правами
    ADMIN_ROLES = {
        TelegramUserRole.ADMIN,
        TelegramUserRole.SENIOR_ADMIN,
        TelegramUserRole.DEVELOPER
    }
    
    @classmethod
    def has_unlimited_access(cls, role: str) -> bool:
        """Проверить, имеет ли роль безлимитный доступ"""
        return role in cls.UNLIMITED_ACCESS_ROLES
    
    @classmethod
    def is_admin(cls, role: str) -> bool:
        """Проверить, является ли роль административной"""
        return role in cls.ADMIN_ROLES
    
    @classmethod
    def get_role_level(cls, role: str) -> int:
        """Получить уровень роли"""
        return cls.ROLE_LEVELS.get(role, 0)
    
    @classmethod
    def can_manage_role(cls, manager_role: str, target_role: str) -> bool:
        """Проверить, может ли роль manager_role управлять target_role"""
        manager_level = cls.get_role_level(manager_role)
        target_level = cls.get_role_level(target_role)
        return manager_level > target_level


class TelegramUserPermissions:
    """Система разрешений для Telegram пользователей"""
    
    # Предопределенные пользователи с ролями
    PREDEFINED_USERS = {
        5699315855: TelegramUserRole.DEVELOPER,      # @infoblog_developer
        7610418399: TelegramUserRole.SENIOR_ADMIN,   # @selecttoolsupport  
        792247608: TelegramUserRole.ADMIN            # @fedor4fingers
    }
    
    @classmethod
    def get_user_role(cls, user_id: int, db_role: Optional[str] = None) -> str:
        """
        Получить роль пользователя
        
        Args:
            user_id: ID пользователя Telegram
            db_role: Роль из базы данных (если есть)
            
        Returns:
            Роль пользователя
        """
        # Сначала проверяем предопределенных пользователей
        if user_id in cls.PREDEFINED_USERS:
            return cls.PREDEFINED_USERS[user_id].value
        
        # Затем роль из базы данных
        if db_role:
            return db_role
        
        # По умолчанию - обычный пользователь
        return TelegramUserRole.USER.value
    
    @classmethod
    def has_unlimited_access(cls, user_id: int, db_role: Optional[str] = None) -> bool:
        """Проверить, имеет ли пользователь безлимитный доступ"""
        role = cls.get_user_role(user_id, db_role)
        return RoleHierarchy.has_unlimited_access(role)
    
    @classmethod
    def is_admin(cls, user_id: int, db_role: Optional[str] = None) -> bool:
        """Проверить, является ли пользователь администратором"""
        role = cls.get_user_role(user_id, db_role)
        return RoleHierarchy.is_admin(role)
    
    @classmethod
    def is_developer(cls, user_id: int, db_role: Optional[str] = None) -> bool:
        """Проверить, является ли пользователь разработчиком"""
        role = cls.get_user_role(user_id, db_role)
        return role == TelegramUserRole.DEVELOPER.value
    
    @classmethod
    def has_admin_access(cls, user_id: int, db_role: Optional[str] = None) -> bool:
        """Проверить, имеет ли пользователь доступ к админ-панели"""
        role = cls.get_user_role(user_id, db_role)
        return role in ['admin', 'senior_admin', 'developer']

    @classmethod
    def can_bypass_limits(cls, user_id: int, db_role: Optional[str] = None) -> bool:
        """Проверить, может ли пользователь обходить лимиты"""
        return cls.has_unlimited_access(user_id, db_role)
    
    @classmethod
    def get_role_display_name(cls, role: str) -> str:
        """Получить отображаемое имя роли"""
        role_names = {
            TelegramUserRole.USER.value: "Пользователь",
            TelegramUserRole.ADMIN.value: "Администратор", 
            TelegramUserRole.SENIOR_ADMIN.value: "Старший администратор",
            TelegramUserRole.DEVELOPER.value: "Разработчик"
        }
        return role_names.get(role, "Неизвестная роль")
    
    @classmethod
    def get_all_roles(cls) -> List[Dict[str, str]]:
        """Получить список всех ролей"""
        return [
            {"value": role.value, "name": cls.get_role_display_name(role.value)}
            for role in TelegramUserRole
        ]


def log_role_action(user_id: int, action: str, details: str = ""):
    """Логировать действие связанное с ролями"""
    logger.info(f"Role action - User: {user_id}, Action: {action}, Details: {details}")


# Декоратор для проверки ролей
def require_role(required_role: TelegramUserRole):
    """
    Декоратор для проверки роли пользователя
    
    Args:
        required_role: Минимально необходимая роль
    """
    def decorator(func):
        async def wrapper(message_or_callback, *args, **kwargs):
            user_id = message_or_callback.from_user.id
            
            # Получаем роль пользователя (здесь нужно будет добавить получение из БД)
            user_role = TelegramUserPermissions.get_user_role(user_id)
            user_level = RoleHierarchy.get_role_level(user_role)
            required_level = RoleHierarchy.get_role_level(required_role.value)
            
            if user_level < required_level:
                # Определяем метод отправки сообщения
                if hasattr(message_or_callback, 'answer'):
                    send_method = message_or_callback.answer
                elif hasattr(message_or_callback, 'message'):
                    send_method = message_or_callback.message.answer
                else:
                    send_method = lambda text: None
                
                await send_method(
                    f"❌ Недостаточно прав доступа. Требуется роль: {TelegramUserPermissions.get_role_display_name(required_role.value)}"
                )
                log_role_action(user_id, "ACCESS_DENIED", f"Required: {required_role.value}, Has: {user_role}")
                return
            
            log_role_action(user_id, "ACCESS_GRANTED", f"Function: {func.__name__}")
            return await func(message_or_callback, *args, **kwargs)
        
        return wrapper
    return decorator


# Декоратор для проверки безлимитного доступа
def require_unlimited_access(func):
    """Декоратор для проверки безлимитного доступа"""
    async def wrapper(message_or_callback, *args, **kwargs):
        user_id = message_or_callback.from_user.id
        
        if not TelegramUserPermissions.has_unlimited_access(user_id):
            # Определяем метод отправки сообщения
            if hasattr(message_or_callback, 'answer'):
                send_method = message_or_callback.answer
            elif hasattr(message_or_callback, 'message'):
                send_method = message_or_callback.message.answer
            else:
                send_method = lambda text: None
            
            await send_method("❌ Функция доступна только администраторам")
            log_role_action(user_id, "UNLIMITED_ACCESS_DENIED", f"Function: {func.__name__}")
            return
        
        log_role_action(user_id, "UNLIMITED_ACCESS_GRANTED", f"Function: {func.__name__}")
        return await func(message_or_callback, *args, **kwargs)
    
    return wrapper
