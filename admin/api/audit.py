"""
API endpoints для просмотра логов аудита
Production-ready версия с улучшенной безопасностью и производительностью
"""
import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from functools import lru_cache

from ..auth.permissions import get_current_active_user, RequireUserView
from ..auth.models import TokenData
from ..services.audit_service import get_audit_service, AuditAction, AuditResource
from ..decorators.audit_decorator import audit_system_action
from database.universal_database import UniversalDatabase

logger = logging.getLogger(__name__)
router = APIRouter()

# Константы для production-ready настроек
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50
MAX_DAYS_FILTER = 365
CACHE_TTL = 300  # 5 минут кеш для статистики


async def get_db(request: Request) -> UniversalDatabase:
    """Получить объект базы данных"""
    return request.state.db


class AuditLogResponse(BaseModel):
    """Ответ с логом аудита (Production-ready версия)"""
    id: int
    admin_user_id: int
    admin_username: Optional[str] = Field(None, max_length=100)
    admin_email: Optional[str] = Field(None, max_length=255)
    action: str = Field(..., min_length=1, max_length=50)
    resource_type: str = Field(..., min_length=1, max_length=50)
    resource_id: Optional[int] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = Field(None, max_length=45)  # IPv6 поддержка
    user_agent: Optional[str] = Field(None, max_length=500)
    created_at: str
    execution_time_ms: Optional[float] = None  # Время выполнения операции

    @validator('ip_address')
    def validate_ip_address(cls, v):
        if v and len(v) > 45:  # Максимальная длина IPv6
            return v[:45]
        return v


class AuditLogsListResponse(BaseModel):
    """Ответ со списком логов аудита (Production-ready версия)"""
    logs: List[AuditLogResponse]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    per_page: int = Field(..., ge=1, le=MAX_PAGE_SIZE)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool
    filters_applied: Dict[str, Any] = {}
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    performance_metrics: Dict[str, float] = {}


class AdminActivityResponse(BaseModel):
    """Ответ с активностью администратора (Production-ready версия)"""
    admin_user_id: int
    username: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    total_actions: int = Field(..., ge=0)
    resource_types_count: int = Field(..., ge=0)
    last_activity: Optional[str] = None
    success_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    actions_by_type: Dict[str, int] = {}
    daily_activity: List[Dict[str, Any]] = []
    risk_score: float = Field(default=0.0, ge=0.0, le=10.0)  # Оценка риска активности


class ResourceActivityResponse(BaseModel):
    """Ответ с активностью по ресурсам"""
    resource_type: str
    action: str
    count: int


@router.get("/logs", response_model=AuditLogsListResponse)
@audit_system_action(AuditAction.VIEW)
async def get_audit_logs(
    page: int = Query(1, ge=1, description="Номер страницы"),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Количество записей на странице"),
    admin_user_id: Optional[int] = Query(None, description="Фильтр по администратору"),
    resource_type: Optional[str] = Query(None, max_length=50, description="Фильтр по типу ресурса"),
    action: Optional[str] = Query(None, max_length=50, description="Фильтр по действию"),
    date_from: Optional[str] = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    success_only: Optional[bool] = Query(None, description="Только успешные операции"),
    sort_by: str = Query("created_at", description="Поле для сортировки"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Порядок сортировки"),
    db: UniversalDatabase = Depends(get_db),
    current_user: TokenData = Depends(RequireUserView)
):
    """
    Получить список логов аудита (Production-ready версия)

    Улучшения:
    - Расширенная фильтрация и сортировка
    - Валидация параметров
    - Метрики производительности
    - Детальное логирование
    """
    start_time = time.time()

    try:
        # Валидация дат
        parsed_date_from = None
        parsed_date_to = None

        if date_from:
            try:
                parsed_date_from = datetime.strptime(date_from, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты date_from. Используйте YYYY-MM-DD"
                )

        if date_to:
            try:
                parsed_date_to = datetime.strptime(date_to, "%Y-%m-%d")
                # Устанавливаем конец дня
                parsed_date_to = parsed_date_to.replace(hour=23, minute=59, second=59)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты date_to. Используйте YYYY-MM-DD"
                )

        # Проверка диапазона дат
        if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Дата начала не может быть больше даты окончания"
            )

        # Ограничение диапазона дат для производительности
        if parsed_date_from and parsed_date_to:
            days_diff = (parsed_date_to - parsed_date_from).days
            if days_diff > MAX_DAYS_FILTER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Максимальный диапазон дат: {MAX_DAYS_FILTER} дней"
                )

        logger.info(
            f"Запрос логов аудита: пользователь={current_user.username}, "
            f"страница={page}, размер={per_page}, фильтры=admin_id:{admin_user_id}, "
            f"resource:{resource_type}, action:{action}, dates:{date_from}-{date_to}"
        )
        audit_service = get_audit_service()

        # Вычисляем offset
        offset = (page - 1) * per_page

        # Подготавливаем расширенные фильтры
        filters = {
            'admin_user_id': admin_user_id,
            'resource_type': resource_type,
            'action': action,
            'date_from': parsed_date_from,
            'date_to': parsed_date_to,
            'success_only': success_only
        }

        # Получаем логи с расширенными параметрами
        query_start = time.time()
        logs_data = await audit_service.get_logs(
            admin_user_id=admin_user_id,
            resource_type=resource_type,
            action=action,
            date_from=parsed_date_from,
            date_to=parsed_date_to,
            success_only=success_only,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=per_page,
            offset=offset
        )
        query_time = time.time() - query_start

        # Получаем общее количество с теми же фильтрами
        count_start = time.time()
        total = await audit_service.get_logs_count(
            admin_user_id=admin_user_id,
            resource_type=resource_type,
            action=action,
            date_from=parsed_date_from,
            date_to=parsed_date_to,
            success_only=success_only
        )
        count_time = time.time() - count_start

        # Преобразуем в модели ответа с дополнительными полями
        logs = []
        for log in logs_data:
            try:
                log_response = AuditLogResponse(
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
                    created_at=log['created_at'],
                    execution_time_ms=log.get('execution_time_ms')
                )
                logs.append(log_response)
            except Exception as e:
                logger.warning(f"Ошибка обработки лога {log.get('id', 'unknown')}: {e}")
                continue

        # Вычисляем метаданные пагинации
        total_pages = (total + per_page - 1) // per_page
        has_next = page < total_pages
        has_prev = page > 1

        # Подготавливаем информацию о примененных фильтрах
        applied_filters = {k: v for k, v in filters.items() if v is not None}

        # Метрики производительности
        total_time = time.time() - start_time
        performance_metrics = {
            'total_execution_time_ms': round(total_time * 1000, 2),
            'query_time_ms': round(query_time * 1000, 2),
            'count_time_ms': round(count_time * 1000, 2),
            'records_processed': len(logs),
            'total_records': total
        }

        logger.info(
            f"Логи аудита получены: {len(logs)} записей из {total}, "
            f"время выполнения: {performance_metrics['total_execution_time_ms']}ms"
        )

        return AuditLogsListResponse(
            logs=logs,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
            filters_applied=applied_filters,
            performance_metrics=performance_metrics
        )

    except HTTPException:
        # Перебрасываем HTTP исключения как есть
        raise
    except Exception as e:
        logger.error(
            f"Критическая ошибка получения логов аудита: {e}",
            exc_info=True,
            extra={
                'user': current_user.username,
                'page': page,
                'per_page': per_page,
                'filters': {
                    'admin_user_id': admin_user_id,
                    'resource_type': resource_type,
                    'action': action
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера при получении логов аудита"
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
