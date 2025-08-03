"""
API эндпоинты для управления сервисом очистки платежей
Production-ready интеграция в админ-панель
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from database.universal_database import UniversalDatabase
from database.db_adapter import get_database
from services.payment_cleanup import PaymentCleanupService, get_cleanup_service
from admin.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payment-cleanup", tags=["Payment Cleanup"])

# Pydantic модели для API
class CleanupStats(BaseModel):
    """Статистика очистки платежей"""
    pending_invoices: int = Field(description="Количество ожидающих платежей")
    expired_invoices: int = Field(description="Количество просроченных платежей")
    oldest_pending: Optional[str] = Field(description="Дата самого старого ожидающего платежа")
    cleanup_needed: bool = Field(description="Требуется ли очистка")
    last_cleanup: Optional[str] = Field(description="Время последней очистки")

class CleanupConfig(BaseModel):
    """Конфигурация сервиса очистки"""
    cleanup_interval: int = Field(300, ge=60, le=3600, description="Интервал очистки в секундах (60-3600)")
    invoice_timeout: int = Field(1800, ge=300, le=7200, description="Таймаут инвойса в секундах (300-7200)")
    auto_cleanup_enabled: bool = Field(True, description="Включена ли автоматическая очистка")
    delete_old_payments: bool = Field(True, description="Удалять ли старые неуспешные платежи")
    old_payments_days: int = Field(7, ge=1, le=30, description="Через сколько дней удалять старые платежи")

class CleanupResult(BaseModel):
    """Результат очистки"""
    success: bool
    expired_found: int
    cancelled: int
    errors: int
    message: str
    execution_time: float

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
    db: UniversalDatabase = Depends(get_database), 
    _=Depends(require_admin)
):
    """Запустить ручную очистку платежей"""
    try:
        start_time = datetime.now()
        add_cleanup_log("INFO", "Запущена ручная очистка платежей")
        
        cleanup_service = get_cleanup_service(db)
        cleanup_stats = await cleanup_service.cleanup_expired_invoices()
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        result = CleanupResult(
            success=True,
            expired_found=cleanup_stats.get('expired_found', 0),
            cancelled=cleanup_stats.get('cancelled', 0),
            errors=cleanup_stats.get('errors', 0),
            message=f"Очистка завершена: найдено {cleanup_stats.get('expired_found', 0)}, отменено {cleanup_stats.get('cancelled', 0)}",
            execution_time=execution_time
        )
        
        global _last_cleanup_result
        _last_cleanup_result = result
        
        add_cleanup_log("INFO", result.message, {
            "expired_found": result.expired_found,
            "cancelled": result.cancelled,
            "errors": result.errors,
            "execution_time": result.execution_time
        })
        
        # Если включено удаление старых платежей, запускаем в фоне
        if _cleanup_config.delete_old_payments:
            background_tasks.add_task(
                cleanup_old_payments_task, 
                cleanup_service, 
                _cleanup_config.old_payments_days
            )
        
        return result
        
    except Exception as e:
        error_msg = f"Ошибка при ручной очистке: {str(e)}"
        logger.error(error_msg)
        add_cleanup_log("ERROR", error_msg)
        
        return CleanupResult(
            success=False,
            expired_found=0,
            cancelled=0,
            errors=1,
            message=error_msg,
            execution_time=0
        )

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
