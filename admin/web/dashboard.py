"""
Веб-страница дашборда
ИСПРАВЛЕНО: Теперь показывает реальную статистику
"""
import logging
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from ..web.auth import get_current_user_from_cookie
from ..auth.models import TokenData
from ..dependencies import get_db
from database.universal_database import UniversalDatabase

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="admin/templates")
router = APIRouter()


async def require_auth(current_user: Optional[TokenData] = Depends(get_current_user_from_cookie)):
    """Middleware для проверки аутентификации"""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
    return current_user


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """
    Главная страница админ-панели
    ИСПРАВЛЕНО: Теперь получает реальную статистику
    """
    try:
        # Инициализируем сервис статистики если нужно
        from services import get_statistics_service, is_statistics_service_initialized, init_statistics_service

        if not is_statistics_service_initialized():
            init_statistics_service(db)

        stats_service = get_statistics_service()

        # Получаем детальную статистику
        detailed_stats = await stats_service.get_detailed_statistics()

        # Подготавливаем данные для шаблона
        template_data = {
            "request": request,
            "current_user": current_user,
            "page_title": "Dashboard",

            # Основные метрики (ИСПРАВЛЕНО: правильные имена переменных для шаблона)
            "total_users": detailed_stats.get('total_users', 0),
            "active_subscriptions": detailed_stats.get('active_subscribers', 0),
            "total_searches": detailed_stats.get('total_requests', 0),  # Исправлено: было search_requests
            "revenue": detailed_stats.get('revenue_month', 0),  # Исправлено: было monthly_revenue

            # Сегодняшние метрики
            "today_users": detailed_stats.get('new_users_today', 0),
            "today_searches": detailed_stats.get('requests_today', 0),
            "today_subscriptions": detailed_stats.get('successful_payments_today', 0),
            "today_revenue": detailed_stats.get('revenue_today', 0),

            # Дополнительные метрики
            "conversion_rate": detailed_stats.get('conversion_rate', 0),
            "avg_requests_per_user": detailed_stats.get('avg_requests_per_user', 0),
            "blocked_users": detailed_stats.get('blocked_users', 0),
            "unlimited_users": detailed_stats.get('unlimited_users', 0),

            # Метрики за периоды
            "new_users_week": detailed_stats.get('new_users_week', 0),
            "new_users_month": detailed_stats.get('new_users_month', 0),
            "requests_week": detailed_stats.get('requests_week', 0),
            "requests_month": detailed_stats.get('requests_month', 0),
            "revenue_week": detailed_stats.get('revenue_week', 0),

            # Статистика платежей
            "payments_today": detailed_stats.get('payments_today', 0),
            "payments_week": detailed_stats.get('payments_week', 0),
            "payments_month": detailed_stats.get('payments_month', 0),
            "successful_payments_week": detailed_stats.get('successful_payments_week', 0),
            "successful_payments_month": detailed_stats.get('successful_payments_month', 0),

            # Статистика рассылок
            "broadcasts_total": detailed_stats.get('broadcasts_total', 0),
            "broadcasts_completed": detailed_stats.get('broadcasts_completed', 0),
            "broadcasts_sent": detailed_stats.get('broadcasts_sent', 0),
            "broadcasts_failed": detailed_stats.get('broadcasts_failed', 0),

            # Топ пользователи
            "top_users": detailed_stats.get('top_users', [])[:5],  # Первые 5

            # Время генерации
            "stats_generated_at": detailed_stats.get('generated_at', 'Неизвестно')
        }

        return templates.TemplateResponse("dashboard/index.html", template_data)

    except Exception as e:
        logger.error(f"Ошибка получения статистики для dashboard: {e}")

        # Возвращаем пустую статистику при ошибке
        template_data = {
            "request": request,
            "current_user": current_user,
            "page_title": "Dashboard",

            # Все метрики = 0 (ИСПРАВЛЕНО: правильные имена переменных)
            "total_users": 0,
            "active_subscriptions": 0,
            "total_searches": 0,  # Исправлено: было search_requests
            "revenue": 0,  # Исправлено: было monthly_revenue
            "today_users": 0,
            "today_searches": 0,
            "today_subscriptions": 0,
            "today_revenue": 0,
            "conversion_rate": 0,
            "avg_requests_per_user": 0,
            "blocked_users": 0,
            "unlimited_users": 0,
            "new_users_week": 0,
            "new_users_month": 0,
            "requests_week": 0,
            "requests_month": 0,
            "revenue_week": 0,
            "payments_today": 0,
            "payments_week": 0,
            "payments_month": 0,
            "successful_payments_week": 0,
            "successful_payments_month": 0,
            "broadcasts_total": 0,
            "broadcasts_completed": 0,
            "broadcasts_sent": 0,
            "broadcasts_failed": 0,
            "top_users": [],
            "stats_generated_at": "Ошибка загрузки",
            "error_message": f"Ошибка загрузки статистики: {str(e)}"
        }

        return templates.TemplateResponse("dashboard/index.html", template_data)
