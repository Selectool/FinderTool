"""
API endpoints для просмотра логов аудита
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..auth.permissions import get_current_active_user, RequireUserView
from ..auth.models import TokenData
from ..services.audit_service import get_audit_service, AuditAction, AuditResource
from ..decorators.audit_decorator import audit_system_action
from database.universal_database import UniversalDatabase

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_db(request: Request) -> UniversalDatabase:
    """Получить объект базы данных"""
    return request.state.db


class AuditLogResponse(BaseModel):
    """Ответ с логом аудита"""
    id: int
    admin_user_id: int
    admin_username: Optional[str] = None
    admin_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[int] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: str


class AuditLogsListResponse(BaseModel):
    """Ответ со списком логов аудита"""
    logs: List[AuditLogResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class AdminActivityResponse(BaseModel):
    """Ответ с активностью администратора"""
    admin_user_id: int
    username: Optional[str] = None
    email: Optional[str] = None
    total_actions: int
    resource_types_count: int
    last_activity: Optional[str] = None


class ResourceActivityResponse(BaseModel):
    """Ответ с активностью по ресурсам"""
    resource_type: str
    action: str
    count: int


@router.get("/logs", response_model=AuditLogsListResponse)
@audit_system_action(AuditAction.VIEW)
async def get_audit_logs(
    page: int = Query(1, ge=1, description="Номер страницы"),
    per_page: int = Query(50, ge=1, le=100, description="Количество записей на странице"),
    admin_user_id: Optional[int] = Query(None, description="Фильтр по администратору"),
    resource_type: Optional[str] = Query(None, description="Фильтр по типу ресурса"),
    action: Optional[str] = Query(None, description="Фильтр по действию"),
    db: UniversalDatabase = Depends(get_db),
    current_user: TokenData = Depends(RequireUserView)
):
    """Получить список логов аудита"""
    try:
        audit_service = get_audit_service()
        
        # Вычисляем offset
        offset = (page - 1) * per_page
        
        # Получаем логи и общее количество
        logs_data = await audit_service.get_logs(
            admin_user_id=admin_user_id,
            resource_type=resource_type,
            action=action,
            limit=per_page,
            offset=offset
        )
        
        total = await audit_service.get_logs_count(
            admin_user_id=admin_user_id,
            resource_type=resource_type,
            action=action
        )
        
        # Преобразуем в модели ответа
        logs = [
            AuditLogResponse(
                id=log['id'],
                admin_user_id=log['admin_user_id'],
                admin_username=log.get('admin_username'),
                admin_email=log.get('admin_email'),
                action=log['action'],
                resource_type=log['resource_type'],
                resource_id=log.get('resource_id'),
                details=log.get('details'),
                ip_address=log.get('ip_address'),
                user_agent=log.get('user_agent'),
                created_at=log['created_at']
            )
            for log in logs_data
        ]
        
        total_pages = (total + per_page - 1) // per_page
        
        return AuditLogsListResponse(
            logs=logs,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения логов аудита: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения логов аудита"
        )


@router.get("/admin-activity", response_model=List[AdminActivityResponse])
@audit_system_action(AuditAction.VIEW)
async def get_admin_activity_stats(
    days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
    db: UniversalDatabase = Depends(get_db),
    current_user: TokenData = Depends(RequireUserView)
):
    """Получить статистику активности администраторов"""
    try:
        audit_service = get_audit_service()
        
        stats_data = await audit_service.get_admin_activity_stats(days=days)
        
        stats = [
            AdminActivityResponse(
                admin_user_id=stat['admin_user_id'],
                username=stat.get('username'),
                email=stat.get('email'),
                total_actions=stat['total_actions'],
                resource_types_count=stat['resource_types_count'],
                last_activity=stat.get('last_activity')
            )
            for stat in stats_data
        ]
        
        return stats
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики активности администраторов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения статистики активности"
        )


@router.get("/resource-activity", response_model=List[ResourceActivityResponse])
@audit_system_action(AuditAction.VIEW)
async def get_resource_activity_stats(
    days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
    db: UniversalDatabase = Depends(get_db),
    current_user: TokenData = Depends(RequireUserView)
):
    """Получить статистику активности по ресурсам"""
    try:
        audit_service = get_audit_service()
        
        stats_data = await audit_service.get_resource_activity_stats(days=days)
        
        stats = [
            ResourceActivityResponse(
                resource_type=stat['resource_type'],
                action=stat['action'],
                count=stat['count']
            )
            for stat in stats_data
        ]
        
        return stats
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики активности по ресурсам: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения статистики активности"
        )


@router.get("/actions")
async def get_available_actions(
    current_user: TokenData = Depends(RequireUserView)
):
    """Получить список доступных действий для фильтрации"""
    return {
        "actions": [
            {"value": AuditAction.CREATE, "name": "Создание"},
            {"value": AuditAction.UPDATE, "name": "Обновление"},
            {"value": AuditAction.DELETE, "name": "Удаление"},
            {"value": AuditAction.VIEW, "name": "Просмотр"},
            {"value": AuditAction.LOGIN, "name": "Вход"},
            {"value": AuditAction.LOGOUT, "name": "Выход"},
            {"value": AuditAction.SEND, "name": "Отправка"},
            {"value": AuditAction.BLOCK, "name": "Блокировка"},
            {"value": AuditAction.UNBLOCK, "name": "Разблокировка"},
            {"value": AuditAction.ROLE_CHANGE, "name": "Изменение роли"},
            {"value": AuditAction.EXPORT, "name": "Экспорт"},
            {"value": AuditAction.IMPORT, "name": "Импорт"}
        ]
    }


@router.get("/resources")
async def get_available_resources(
    current_user: TokenData = Depends(RequireUserView)
):
    """Получить список доступных ресурсов для фильтрации"""
    return {
        "resources": [
            {"value": AuditResource.USER, "name": "Пользователи"},
            {"value": AuditResource.BROADCAST, "name": "Рассылки"},
            {"value": AuditResource.TEMPLATE, "name": "Шаблоны"},
            {"value": AuditResource.ROLE, "name": "Роли"},
            {"value": AuditResource.ADMIN_USER, "name": "Администраторы"},
            {"value": AuditResource.SYSTEM, "name": "Система"},
            {"value": AuditResource.STATISTICS, "name": "Статистика"}
        ]
    }


@router.post("/cleanup")
@audit_system_action(AuditAction.DELETE)
async def cleanup_old_logs(
    days: int = Query(90, ge=30, le=365, description="Количество дней для хранения логов"),
    db: UniversalDatabase = Depends(get_db),
    current_user: TokenData = Depends(RequireUserView)
):
    """Очистить старые логи аудита"""
    try:
        # Проверяем права (только разработчики могут очищать логи)
        if current_user.role != 'developer':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только разработчики могут очищать логи аудита"
            )
        
        audit_service = get_audit_service()
        deleted_count = await audit_service.cleanup_old_logs(days=days)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": f"Удалено {deleted_count} старых записей логов",
                "deleted_count": deleted_count,
                "retention_days": days
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка очистки старых логов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при очистке логов"
        )
