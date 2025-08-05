"""
Декораторы для автоматического логирования действий администраторов
"""
import functools
import logging
from typing import Optional, Dict, Any, Callable
from fastapi import Request
from inspect import signature

from ..services.audit_service import get_audit_service, AuditAction, AuditResource
from ..auth.models import TokenData

logger = logging.getLogger(__name__)


def audit_log(
    action: str,
    resource_type: str,
    resource_id_param: Optional[str] = None,
    details_extractor: Optional[Callable] = None,
    success_only: bool = True
):
    """
    Декоратор для автоматического логирования действий администраторов
    
    Args:
        action: Тип действия (CREATE, UPDATE, DELETE, etc.)
        resource_type: Тип ресурса (user, broadcast, etc.)
        resource_id_param: Имя параметра, содержащего ID ресурса
        details_extractor: Функция для извлечения дополнительных деталей
        success_only: Логировать только успешные операции
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Извлекаем необходимые данные
            request = None
            current_user = None
            resource_id = None
            
            # Ищем Request и TokenData в аргументах
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif isinstance(arg, TokenData):
                    current_user = arg
            
            # Ищем в kwargs
            for key, value in kwargs.items():
                if isinstance(value, Request):
                    request = value
                elif isinstance(value, TokenData):
                    current_user = value
                elif key == resource_id_param:
                    resource_id = value
            
            # Если не нашли current_user, пытаемся найти его в зависимостях
            if not current_user:
                # Получаем сигнатуру функции
                sig = signature(func)
                for param_name, param in sig.parameters.items():
                    if param_name in kwargs and hasattr(kwargs[param_name], 'user_id'):
                        current_user = kwargs[param_name]
                        break
            
            # Выполняем основную функцию
            try:
                result = await func(*args, **kwargs)
                
                # Логируем только если операция успешна или success_only=False
                if not success_only or (result and not hasattr(result, 'status_code') or 
                                      (hasattr(result, 'status_code') and result.status_code < 400)):
                    await _log_action(
                        current_user=current_user,
                        request=request,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        details_extractor=details_extractor,
                        func_args=args,
                        func_kwargs=kwargs,
                        result=result
                    )
                
                return result
                
            except Exception as e:
                # Логируем ошибки если success_only=False
                if not success_only:
                    await _log_action(
                        current_user=current_user,
                        request=request,
                        action=f"{action}_FAILED",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        details_extractor=lambda *a, **k: {"error": str(e)},
                        func_args=args,
                        func_kwargs=kwargs,
                        result=None
                    )
                raise
        
        return wrapper
    return decorator


async def _log_action(
    current_user: Optional[TokenData],
    request: Optional[Request],
    action: str,
    resource_type: str,
    resource_id: Optional[int],
    details_extractor: Optional[Callable],
    func_args: tuple,
    func_kwargs: dict,
    result: Any
):
    """Внутренняя функция для логирования действия"""
    try:
        if not current_user:
            logger.warning(f"Cannot log action {action}: no current user found")
            return
        
        audit_service = get_audit_service()
        
        # Извлекаем дополнительные детали
        details = {}
        if details_extractor:
            try:
                details = details_extractor(func_args, func_kwargs, result)
            except Exception as e:
                logger.error(f"Error extracting audit details: {e}")
                details = {"details_extraction_error": str(e)}
        
        # Извлекаем IP и User-Agent из запроса
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        
        # Логируем действие
        await audit_service.log_action(
            admin_user_id=current_user.user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
    except Exception as e:
        logger.error(f"Failed to log audit action: {e}")


# Предопределенные декораторы для частых операций
def audit_user_action(action: str, resource_id_param: str = "user_id"):
    """Декоратор для действий с пользователями"""
    return audit_log(
        action=action,
        resource_type=AuditResource.USER,
        resource_id_param=resource_id_param,
        details_extractor=lambda args, kwargs, result: {
            "user_id": kwargs.get(resource_id_param),
            "action_details": _extract_user_details(kwargs, result)
        }
    )


def audit_broadcast_action(action: str, resource_id_param: str = "broadcast_id"):
    """Декоратор для действий с рассылками"""
    return audit_log(
        action=action,
        resource_type=AuditResource.BROADCAST,
        resource_id_param=resource_id_param,
        details_extractor=lambda args, kwargs, result: {
            "broadcast_id": kwargs.get(resource_id_param),
            "action_details": _extract_broadcast_details(kwargs, result)
        }
    )


def audit_role_action(action: str, resource_id_param: str = "user_id"):
    """Декоратор для действий с ролями"""
    return audit_log(
        action=action,
        resource_type=AuditResource.ROLE,
        resource_id_param=resource_id_param,
        details_extractor=lambda args, kwargs, result: {
            "user_id": kwargs.get(resource_id_param),
            "role_details": _extract_role_details(kwargs, result)
        }
    )


def audit_template_action(action: str, resource_id_param: str = "template_id"):
    """Декоратор для действий с шаблонами"""
    return audit_log(
        action=action,
        resource_type=AuditResource.TEMPLATE,
        resource_id_param=resource_id_param,
        details_extractor=lambda args, kwargs, result: {
            "template_id": kwargs.get(resource_id_param),
            "template_details": _extract_template_details(kwargs, result)
        }
    )


def audit_system_action(action: str):
    """Декоратор для системных действий"""
    return audit_log(
        action=action,
        resource_type=AuditResource.SYSTEM,
        details_extractor=lambda args, kwargs, result: {
            "system_action": action,
            "details": _extract_system_details(kwargs, result)
        }
    )


# Вспомогательные функции для извлечения деталей
def _extract_user_details(kwargs: dict, result: Any) -> dict:
    """Извлечь детали действий с пользователями"""
    details = {}
    
    # Извлекаем данные из запроса
    if 'request' in kwargs and hasattr(kwargs['request'], 'json'):
        try:
            request_data = kwargs['request'].json()
            if 'new_role' in request_data:
                details['new_role'] = request_data['new_role']
            if 'reason' in request_data:
                details['reason'] = request_data['reason']
        except:
            pass
    
    # Извлекаем данные из других параметров
    for key in ['notes', 'reason', 'new_role', 'old_role']:
        if key in kwargs:
            details[key] = kwargs[key]
    
    return details


def _extract_broadcast_details(kwargs: dict, result: Any) -> dict:
    """Извлечь детали действий с рассылками"""
    details = {}
    
    for key in ['message_text', 'target_type', 'scheduled_at', 'template_id']:
        if key in kwargs:
            details[key] = kwargs[key]
    
    return details


def _extract_role_details(kwargs: dict, result: Any) -> dict:
    """Извлечь детали действий с ролями"""
    details = {}
    
    for key in ['new_role', 'old_role', 'reason']:
        if key in kwargs:
            details[key] = kwargs[key]
    
    return details


def _extract_template_details(kwargs: dict, result: Any) -> dict:
    """Извлечь детали действий с шаблонами"""
    details = {}
    
    for key in ['name', 'content', 'category']:
        if key in kwargs:
            details[key] = kwargs[key]
    
    return details


def _extract_system_details(kwargs: dict, result: Any) -> dict:
    """Извлечь детали системных действий"""
    details = {}
    
    # Добавляем общую информацию
    if result and hasattr(result, '__dict__'):
        details['result_type'] = type(result).__name__
    
    return details
