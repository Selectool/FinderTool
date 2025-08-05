"""
Production-ready страница статистики
Детальная аналитика и метрики системы
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict, Any

from ..web.auth import get_current_user_from_cookie
from ..auth.models import TokenData
from ..dependencies import get_db
from database.universal_database import UniversalDatabase

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="admin/templates")
router = APIRouter()


async def require_auth(current_user: Optional[TokenData] = Depends(get_current_user_from_cookie)):
    """Middleware для проверки аутентификации (ИСПРАВЛЕНО)"""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
    return current_user


@router.get("/", response_class=HTMLResponse)
async def statistics_page(
    request: Request,
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """
    Production-ready страница детальной статистики
    """
    try:
        # Инициализируем сервис статистики
        from services import get_statistics_service, is_statistics_service_initialized, init_statistics_service
        
        if not is_statistics_service_initialized():
            init_statistics_service(db)
        
        stats_service = get_statistics_service()
        
        # Получаем детальную статистику
        detailed_stats = await stats_service.get_detailed_statistics()
        
        # Получаем статистику платежей
        payment_stats = await stats_service.get_payment_statistics()
        
        # Получаем health check
        health_status = await stats_service.get_health_status()
        
        # Подготавливаем данные для шаблона
        template_data = {
            "request": request,
            "current_user": current_user,
            "page_title": "Детальная статистика",
            
            # === ОСНОВНЫЕ МЕТРИКИ ===
            "overview": {
                "total_users": detailed_stats.get('total_users', 0),
                "active_subscribers": detailed_stats.get('active_subscribers', 0),
                "total_requests": detailed_stats.get('total_requests', 0),
                "total_revenue": detailed_stats.get('revenue_month', 0),
                "conversion_rate": detailed_stats.get('conversion_rate', 0),
                "avg_requests_per_user": detailed_stats.get('avg_requests_per_user', 0)
            },
            
            # === ПОЛЬЗОВАТЕЛИ ===
            "users": {
                "total": detailed_stats.get('total_users', 0),
                "active_subscribers": detailed_stats.get('active_subscribers', 0),
                "blocked": detailed_stats.get('blocked_users', 0),
                "unlimited": detailed_stats.get('unlimited_users', 0),
                "new_today": detailed_stats.get('new_users_today', 0),
                "new_week": detailed_stats.get('new_users_week', 0),
                "new_month": detailed_stats.get('new_users_month', 0)
            },
            
            # === ЗАПРОСЫ ===
            "requests": {
                "total": detailed_stats.get('total_requests', 0),
                "today": detailed_stats.get('requests_today', 0),
                "week": detailed_stats.get('requests_week', 0),
                "month": detailed_stats.get('requests_month', 0),
                "avg_per_user": detailed_stats.get('avg_requests_per_user', 0)
            },
            
            # === ПЛАТЕЖИ ===
            "payments": {
                "today": {
                    "count": payment_stats.get('today', {}).get('count', 0),
                    "successful": payment_stats.get('today', {}).get('successful', 0),
                    "amount": payment_stats.get('today', {}).get('amount', 0) // 100,
                    "pending": payment_stats.get('today', {}).get('pending', 0),
                    "failed": payment_stats.get('today', {}).get('failed', 0)
                },
                "week": {
                    "count": payment_stats.get('week', {}).get('count', 0),
                    "successful": payment_stats.get('week', {}).get('successful', 0),
                    "amount": payment_stats.get('week', {}).get('amount', 0) // 100,
                    "pending": payment_stats.get('week', {}).get('pending', 0),
                    "failed": payment_stats.get('week', {}).get('failed', 0)
                },
                "month": {
                    "count": payment_stats.get('month', {}).get('count', 0),
                    "successful": payment_stats.get('month', {}).get('successful', 0),
                    "amount": payment_stats.get('month', {}).get('amount', 0) // 100,
                    "pending": payment_stats.get('month', {}).get('pending', 0),
                    "failed": payment_stats.get('month', {}).get('failed', 0)
                },
                "total": {
                    "count": payment_stats.get('total', {}).get('count', 0),
                    "successful": payment_stats.get('total', {}).get('successful', 0),
                    "amount": payment_stats.get('total', {}).get('amount', 0) // 100,
                    "pending": payment_stats.get('total', {}).get('pending', 0),
                    "failed": payment_stats.get('total', {}).get('failed', 0)
                }
            },
            
            # === РАССЫЛКИ ===
            "broadcasts": {
                "total": detailed_stats.get('broadcasts_total', 0),
                "completed": detailed_stats.get('broadcasts_completed', 0),
                "sent": detailed_stats.get('broadcasts_sent', 0),
                "failed": detailed_stats.get('broadcasts_failed', 0),
                "success_rate": 0
            },
            
            # === ТОП ПОЛЬЗОВАТЕЛИ ===
            "top_users": detailed_stats.get('top_users', [])[:10],
            
            # === СИСТЕМА ===
            "system": {
                "health_status": health_status.get('status', 'unknown'),
                "database_connected": health_status.get('database_connected', False),
                "cache_size": health_status.get('cache_size', 0),
                "cache_ttl": health_status.get('cache_ttl', 0),
                "validation_enabled": health_status.get('validation_enabled', False)
            },
            
            # === ВРЕМЕННЫЕ МЕТКИ ===
            "timestamps": {
                "generated_at": detailed_stats.get('generated_at', datetime.now().isoformat()),
                "health_checked_at": health_status.get('timestamp', datetime.now().isoformat()),
                "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            
            # === ДОПОЛНИТЕЛЬНЫЕ РАСЧЕТЫ ===
            "calculated": {
                "user_growth_rate": 0,  # Будет рассчитано в шаблоне
                "revenue_per_user": 0,  # Будет рассчитано в шаблоне
                "payment_success_rate": 0,  # Будет рассчитано в шаблоне
                "daily_avg_requests": 0  # Будет рассчитано в шаблоне
            }
        }
        
        # Дополнительные расчеты
        if template_data["users"]["total"] > 0:
            template_data["calculated"]["revenue_per_user"] = round(
                template_data["payments"]["total"]["amount"] / template_data["users"]["total"], 2
            )
        
        total_payments = template_data["payments"]["total"]["count"]
        successful_payments = template_data["payments"]["total"]["successful"]
        if total_payments > 0:
            template_data["calculated"]["payment_success_rate"] = round(
                (successful_payments / total_payments) * 100, 1
            )
        
        # Расчет success rate для рассылок
        total_broadcast_messages = template_data["broadcasts"]["sent"] + template_data["broadcasts"]["failed"]
        if total_broadcast_messages > 0:
            template_data["broadcasts"]["success_rate"] = round(
                (template_data["broadcasts"]["sent"] / total_broadcast_messages) * 100, 1
            )
        
        logger.info(f"Статистика загружена для пользователя {current_user.username}")
        
        return templates.TemplateResponse("statistics/index.html", template_data)
        
    except Exception as e:
        logger.error(f"Ошибка загрузки статистики: {e}")
        
        # Возвращаем страницу с ошибкой
        error_data = {
            "request": request,
            "current_user": current_user,
            "page_title": "Ошибка статистики",
            "error": {
                "message": "Не удалось загрузить статистику",
                "details": str(e),
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }
        
        return templates.TemplateResponse("statistics/error.html", error_data)


@router.get("/api/data")
async def statistics_api_data(
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """
    API endpoint для получения данных статистики (для AJAX обновлений)
    """
    try:
        from services import get_statistics_service, is_statistics_service_initialized, init_statistics_service
        
        if not is_statistics_service_initialized():
            init_statistics_service(db)
        
        stats_service = get_statistics_service()
        
        # Получаем все данные
        detailed_stats = await stats_service.get_detailed_statistics()
        payment_stats = await stats_service.get_payment_statistics()
        health_status = await stats_service.get_health_status()
        
        return {
            "success": True,
            "data": {
                "detailed_stats": detailed_stats,
                "payment_stats": payment_stats,
                "health_status": health_status,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка API статистики: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/refresh")
async def refresh_statistics(
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """
    Принудительное обновление кеша статистики
    """
    try:
        from services import get_statistics_service
        
        stats_service = get_statistics_service()
        await stats_service.invalidate_cache()
        
        logger.info(f"Кеш статистики обновлен пользователем {current_user.username}")
        
        return {
            "success": True,
            "message": "Кеш статистики обновлен",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка обновления кеша: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
