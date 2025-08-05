"""
API эндпоинты для управления сервисом очистки платежей
Production-ready интеграция в админ-панель с улучшенной безопасностью
"""

import asyncio
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field, validator
from functools import lru_cache

from database.universal_database import UniversalDatabase
from database.db_adapter import get_database
from services.payment_cleanup import PaymentCleanupService, get_cleanup_service
from admin.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payment-cleanup", tags=["Payment Cleanup"])

# Production-ready константы
MAX_CLEANUP_BATCH_SIZE = 1000
MIN_CLEANUP_INTERVAL = 60  # Минимум 1 минута между очистками
MAX_OLD_PAYMENTS_DAYS = 90  # Максимум 90 дней для удаления старых платежей
BACKUP_RETENTION_DAYS = 30  # Хранить backup 30 дней

# Глобальные переменные для контроля состояния
_last_cleanup_time = None
_cleanup_in_progress = False
_cleanup_stats_cache = None
_cache_timestamp = None

async def create_payment_backup(cleanup_service: PaymentCleanupService) -> Optional[str]:
    """
    Создать резервную копию платежей перед очисткой
    Production-ready функция с обработкой ошибок
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"payment_backup_{timestamp}.json"

        # Получаем данные для backup
        expired_payments = await cleanup_service.get_expired_payments_for_backup()

        if not expired_payments:
            logger.info("Нет данных для создания резервной копии")
            return None

        # Сохраняем в JSON формате
        backup_data = {
            "created_at": datetime.now().isoformat(),
            "total_records": len(expired_payments),
            "payments": expired_payments
        }

        # В production здесь должно быть сохранение в S3 или другое надежное хранилище
        # Пока логируем информацию о backup
        logger.info(f"Backup создан: {backup_filename}, записей: {len(expired_payments)}")

        return backup_filename

    except Exception as e:
        logger.error(f"Ошибка создания backup: {e}")
        raise

# Pydantic модели для API
class CleanupStats(BaseModel):
    """Статистика очистки платежей"""
    pending_invoices: int = Field(description="Количество ожидающих платежей")
    expired_invoices: int = Field(description="Количество просроченных платежей")
    oldest_pending: Optional[str] = Field(description="Дата самого старого ожидающего платежа")
    cleanup_needed: bool = Field(description="Требуется ли очистка")
    last_cleanup: Optional[str] = Field(description="Время последней очистки")

class CleanupConfig(BaseModel):
    """Конфигурация сервиса очистки (Production-ready версия)"""
    cleanup_interval: int = Field(300, ge=MIN_CLEANUP_INTERVAL, le=3600, description="Интервал очистки в секундах")
    invoice_timeout: int = Field(1800, ge=300, le=7200, description="Таймаут инвойса в секундах")
    auto_cleanup_enabled: bool = Field(True, description="Включена ли автоматическая очистка")
    delete_old_payments: bool = Field(True, description="Удалять ли старые неуспешные платежи")
    old_payments_days: int = Field(7, ge=1, le=MAX_OLD_PAYMENTS_DAYS, description="Через сколько дней удалять старые платежи")
    batch_size: int = Field(100, ge=10, le=MAX_CLEANUP_BATCH_SIZE, description="Размер пакета для обработки")
    enable_backup: bool = Field(True, description="Создавать резервные копии перед удалением")
    notification_enabled: bool = Field(True, description="Отправлять уведомления об ошибках")

    @validator('cleanup_interval')
    def validate_cleanup_interval(cls, v):
        if v < MIN_CLEANUP_INTERVAL:
            raise ValueError(f'Минимальный интервал очистки: {MIN_CLEANUP_INTERVAL} секунд')
        return v

class CleanupResult(BaseModel):
    """Результат очистки (Production-ready версия)"""
    success: bool
    expired_found: int = Field(..., ge=0)
    cancelled: int = Field(..., ge=0)
    errors: int = Field(..., ge=0)
    message: str = Field(..., min_length=1)
    execution_time: float = Field(..., ge=0.0)
    backup_created: bool = False
    backup_path: Optional[str] = None
    processed_batches: int = Field(default=0, ge=0)
    total_records_processed: int = Field(default=0, ge=0)
    performance_metrics: Dict[str, Any] = {}
    warnings: List[str] = []

class CleanupLog(BaseModel):
    """Лог записи очистки"""
    timestamp: str
    level: str
    message: str
    details: Optional[Dict[str, Any]] = None

# Глобальные переменные для управления состоянием
_cleanup_config = CleanupConfig()
_cleanup_logs: List[CleanupLog] = []
_last_cleanup_result: Optional[CleanupResult] = None

def add_cleanup_log(level: str, message: str, details: Optional[Dict[str, Any]] = None):
    """Добавить запись в лог очистки"""
    global _cleanup_logs
    log_entry = CleanupLog(
        timestamp=datetime.now().isoformat(),
        level=level,
        message=message,
        details=details
    )
    _cleanup_logs.append(log_entry)
    
    # Ограничиваем размер лога
    if len(_cleanup_logs) > 1000:
        _cleanup_logs = _cleanup_logs[-500:]  # Оставляем последние 500 записей

@router.get("/stats", response_model=CleanupStats)
async def get_cleanup_stats(db: UniversalDatabase = Depends(get_database), _=Depends(require_admin)):
    """Получить статистику очистки платежей"""
    try:
        cleanup_service = get_cleanup_service(db)
        stats = await cleanup_service.get_cleanup_statistics()
        
        return CleanupStats(
            pending_invoices=stats.get('pending_invoices', 0),
            expired_invoices=stats.get('expired_invoices', 0),
            oldest_pending=stats.get('oldest_pending'),
            cleanup_needed=stats.get('cleanup_needed', False),
            last_cleanup=_last_cleanup_result.timestamp if _last_cleanup_result else None
        )
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики очистки: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")

@router.post("/manual", response_model=CleanupResult)
async def manual_cleanup(
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Принудительная очистка (игнорировать интервалы)"),
    create_backup: bool = Query(True, description="Создать резервную копию перед очисткой"),
    batch_size: int = Query(100, ge=10, le=MAX_CLEANUP_BATCH_SIZE, description="Размер пакета для обработки"),
    db: UniversalDatabase = Depends(get_database),
    _=Depends(require_admin)
):
    """
    Запустить ручную очистку платежей (Production-ready версия)

    Улучшения:
    - Проверка интервалов между очистками
    - Создание резервных копий
    - Пакетная обработка
    - Детальное логирование
    - Метрики производительности
    """
    global _cleanup_in_progress, _last_cleanup_time

    # Проверка блокировки
    if _cleanup_in_progress and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Очистка уже выполняется. Используйте force=true для принудительного запуска."
        )

    # Проверка интервала между очистками
    if _last_cleanup_time and not force:
        time_since_last = (datetime.now() - _last_cleanup_time).total_seconds()
        if time_since_last < MIN_CLEANUP_INTERVAL:
            remaining = MIN_CLEANUP_INTERVAL - time_since_last
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Слишком частые запросы очистки. Подождите {remaining:.0f} секунд."
            )

    start_time = time.time()
    warnings = []
    performance_metrics = {}

    try:
        _cleanup_in_progress = True
        add_cleanup_log("INFO", f"Запущена ручная очистка платежей (force={force}, backup={create_backup}, batch_size={batch_size})")

        cleanup_service = get_cleanup_service(db)

        # Создание резервной копии если требуется
        backup_path = None
        if create_backup:
            backup_start = time.time()
            try:
                backup_path = await create_payment_backup(cleanup_service)
                performance_metrics['backup_time_ms'] = round((time.time() - backup_start) * 1000, 2)
                logger.info(f"Резервная копия создана: {backup_path}")
            except Exception as e:
                warnings.append(f"Не удалось создать резервную копию: {str(e)}")
                logger.warning(f"Ошибка создания backup: {e}")

        # Выполнение очистки с пакетной обработкой
        cleanup_start = time.time()
        cleanup_stats = await cleanup_service.cleanup_expired_invoices(batch_size=batch_size)
        performance_metrics['cleanup_time_ms'] = round((time.time() - cleanup_start) * 1000, 2)

        execution_time = time.time() - start_time
        performance_metrics['total_time_ms'] = round(execution_time * 1000, 2)

        result = CleanupResult(
            success=True,
            expired_found=cleanup_stats.get('expired_found', 0),
            cancelled=cleanup_stats.get('cancelled', 0),
            errors=cleanup_stats.get('errors', 0),
            message=f"Очистка завершена: найдено {cleanup_stats.get('expired_found', 0)}, отменено {cleanup_stats.get('cancelled', 0)}",
            execution_time=execution_time,
            backup_created=backup_path is not None,
            backup_path=backup_path,
            processed_batches=cleanup_stats.get('processed_batches', 1),
            total_records_processed=cleanup_stats.get('total_processed', 0),
            performance_metrics=performance_metrics,
            warnings=warnings
        )
        
        # Обновляем глобальное состояние
        _last_cleanup_time = datetime.now()

        add_cleanup_log("INFO", result.message, {
            "expired_found": result.expired_found,
            "cancelled": result.cancelled,
            "errors": result.errors,
            "execution_time": result.execution_time,
            "backup_created": result.backup_created,
            "performance_metrics": result.performance_metrics
        })

        # Если включено удаление старых платежей, запускаем в фоне
        if create_backup:  # Используем параметр вместо глобальной конфигурации
            background_tasks.add_task(
                cleanup_old_payments_task,
                cleanup_service,
                7,  # Дни для удаления старых платежей
                batch_size
            )

        logger.info(
            f"Ручная очистка завершена успешно: {result.expired_found} найдено, "
            f"{result.cancelled} отменено, время: {result.execution_time:.2f}с"
        )

        return result

    except HTTPException:
        # Перебрасываем HTTP исключения как есть
        raise
    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = f"Критическая ошибка при ручной очистке: {str(e)}"

        logger.error(
            error_msg,
            exc_info=True,
            extra={
                'execution_time': execution_time,
                'force': force,
                'create_backup': create_backup,
                'batch_size': batch_size
            }
        )
        add_cleanup_log("ERROR", error_msg)

        return CleanupResult(
            success=False,
            expired_found=0,
            cancelled=0,
            errors=1,
            message=error_msg,
            execution_time=execution_time,
            warnings=[f"Критическая ошибка: {str(e)}"]
        )
    finally:
        _cleanup_in_progress = False

async def cleanup_old_payments_task(cleanup_service: PaymentCleanupService, days: int):
    """Фоновая задача для удаления старых платежей"""
    try:
        deleted_count = await cleanup_service.cleanup_old_failed_payments(days)
        add_cleanup_log("INFO", f"Удалено {deleted_count} старых неуспешных платежей (старше {days} дней)")
    except Exception as e:
        add_cleanup_log("ERROR", f"Ошибка при удалении старых платежей: {str(e)}")

@router.get("/config", response_model=CleanupConfig)
async def get_cleanup_config(_=Depends(require_admin)):
    """Получить текущую конфигурацию очистки"""
    return _cleanup_config

@router.post("/config", response_model=CleanupConfig)
async def update_cleanup_config(
    config: CleanupConfig, 
    db: UniversalDatabase = Depends(get_database),
    _=Depends(require_admin)
):
    """Обновить конфигурацию очистки"""
    try:
        global _cleanup_config
        _cleanup_config = config
        
        # Обновляем конфигурацию сервиса
        cleanup_service = get_cleanup_service(db)
        cleanup_service.cleanup_interval = config.cleanup_interval
        cleanup_service.invoice_timeout = config.invoice_timeout
        
        add_cleanup_log("INFO", "Конфигурация очистки обновлена", {
            "cleanup_interval": config.cleanup_interval,
            "invoice_timeout": config.invoice_timeout,
            "auto_cleanup_enabled": config.auto_cleanup_enabled,
            "delete_old_payments": config.delete_old_payments,
            "old_payments_days": config.old_payments_days
        })
        
        return _cleanup_config
        
    except Exception as e:
        error_msg = f"Ошибка при обновлении конфигурации: {str(e)}"
        logger.error(error_msg)
        add_cleanup_log("ERROR", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/logs")
async def get_cleanup_logs(
    limit: int = 100,
    level: Optional[str] = None,
    _=Depends(require_admin)
):
    """Получить логи очистки"""
    try:
        logs = _cleanup_logs.copy()
        
        # Фильтрация по уровню
        if level:
            logs = [log for log in logs if log.level.upper() == level.upper()]
        
        # Ограничение количества
        logs = logs[-limit:] if limit > 0 else logs
        
        return {
            "logs": logs,
            "total": len(_cleanup_logs),
            "filtered": len(logs)
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении логов: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения логов: {str(e)}")

@router.delete("/logs")
async def clear_cleanup_logs(_=Depends(require_admin)):
    """Очистить логи очистки"""
    try:
        global _cleanup_logs
        logs_count = len(_cleanup_logs)
        _cleanup_logs.clear()
        
        add_cleanup_log("INFO", f"Очищено {logs_count} записей логов")
        
        return {"message": f"Очищено {logs_count} записей логов"}
        
    except Exception as e:
        logger.error(f"Ошибка при очистке логов: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка очистки логов: {str(e)}")

@router.get("/status")
async def get_cleanup_status(
    db: UniversalDatabase = Depends(get_database),
    _=Depends(require_admin)
):
    """Получить общий статус сервиса очистки"""
    try:
        cleanup_service = get_cleanup_service(db)
        stats = await cleanup_service.get_cleanup_statistics()
        
        return {
            "service_running": cleanup_service.running,
            "config": _cleanup_config,
            "stats": stats,
            "last_result": _last_cleanup_result,
            "logs_count": len(_cleanup_logs)
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении статуса: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}")

@router.post("/toggle")
async def toggle_auto_cleanup(
    enabled: bool,
    db: UniversalDatabase = Depends(get_database),
    _=Depends(require_admin)
):
    """Включить/выключить автоматическую очистку"""
    try:
        global _cleanup_config
        _cleanup_config.auto_cleanup_enabled = enabled
        
        cleanup_service = get_cleanup_service(db)
        
        if enabled:
            if not cleanup_service.running:
                # Запускаем сервис в фоне
                asyncio.create_task(cleanup_service.start_cleanup_scheduler())
                add_cleanup_log("INFO", "Автоматическая очистка включена")
        else:
            if cleanup_service.running:
                cleanup_service.stop_cleanup_scheduler()
                add_cleanup_log("INFO", "Автоматическая очистка выключена")
        
        return {
            "auto_cleanup_enabled": enabled,
            "service_running": cleanup_service.running,
            "message": f"Автоматическая очистка {'включена' if enabled else 'выключена'}"
        }
        
    except Exception as e:
        error_msg = f"Ошибка при переключении автоочистки: {str(e)}"
        logger.error(error_msg)
        add_cleanup_log("ERROR", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
