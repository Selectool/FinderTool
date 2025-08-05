"""
API endpoints для статистики
"""
from fastapi import APIRouter, Depends, Request
from typing import List, Dict, Any
from datetime import datetime, timedelta

from ..auth.permissions import RequireStatisticsView, log_admin_action
from database.universal_database import UniversalDatabase

router = APIRouter()


async def get_db(request: Request) -> UniversalDatabase:
    """Получить объект базы данных"""
    return request.state.db


@router.get("/dashboard")
@log_admin_action("view_dashboard_stats", "statistics")
async def get_dashboard_stats(
    current_user = Depends(RequireStatisticsView),
    db: UniversalDatabase = Depends(get_db)
) -> Dict[str, Any]:
    """
    Получить статистику для dashboard
    ИСПРАВЛЕНО: Использует новый StatisticsService
    """
    try:
        from services import get_statistics_service, is_statistics_service_initialized, init_statistics_service

        # Инициализируем сервис статистики если не инициализирован
        if not is_statistics_service_initialized():
            init_statistics_service(db)

        stats_service = get_statistics_service()

        # Получаем детальную статистику
        stats = await stats_service.get_detailed_statistics()

        if not stats:
            # Возвращаем пустую статистику при ошибке
            return {
                "summary": {
                    "total_users": 0,
                    "active_subscriptions": 0,
                    "search_requests": 0,
                    "monthly_revenue": 0,
                    "today_users": 0,
                    "today_searches": 0,
                    "today_subscriptions": 0,
                    "today_revenue": 0,
                    "conversion_rate": 0.0,
                    "avg_requests_per_user": 0.0,
                    "broadcast_success_rate": 0.0
                },
                "charts": {
                    "user_growth": [],
                    "request_activity": [],
                    "daily_stats": []
                },
                "top_users": [],
                "recent_activity": [],
                "system_health": {"status": "error"},
                "generated_at": datetime.now().isoformat()
            }

        # Получаем данные для графиков активности (пока используем старый метод)
        try:
            activity_data = await db.get_user_activity_chart_data(days=30)
            chart_data = process_activity_data(activity_data)
        except:
            chart_data = {
                "user_growth": [],
                "request_activity": [],
                "daily_stats": []
            }

        # Вычисляем дополнительные метрики
        total_users = stats.get("total_users", 0)
        active_subscribers = stats.get("active_subscribers", 0)
        total_requests = stats.get("total_requests", 0)

        # Конверсия в подписчики
        conversion_rate = 0.0
        if total_users > 0:
            conversion_rate = round((active_subscribers / total_users) * 100, 2)

        # Средние запросы на пользователя
        avg_requests_per_user = 0.0
        if total_users > 0:
            avg_requests_per_user = round(total_requests / total_users, 2)

        # Эффективность рассылок
        broadcast_success_rate = 0.0
        total_sent = stats.get("broadcasts_sent", 0) or 0
        total_failed = stats.get("broadcasts_failed", 0) or 0
        if total_sent + total_failed > 0:
            broadcast_success_rate = round((total_sent / (total_sent + total_failed)) * 100, 2)

        return {
            "summary": {
                "total_users": total_users,
                "active_subscriptions": active_subscribers,
                "search_requests": total_requests,
                "monthly_revenue": stats.get("revenue_month", 0),
                "today_users": stats.get("new_users_today", 0),
                "today_searches": stats.get("requests_today", 0),
                "today_subscriptions": stats.get("successful_payments_today", 0),
                "today_revenue": stats.get("revenue_today", 0),
                "conversion_rate": conversion_rate,
                "avg_requests_per_user": avg_requests_per_user,
                "broadcast_success_rate": broadcast_success_rate
            },
            "overview": {
                "total_users": total_users,
                "active_subscribers": active_subscribers,
                "unlimited_users": stats.get("unlimited_users", 0),
                "blocked_users": stats.get("blocked_users", 0),
                "new_users_today": stats.get("new_users_today", 0),
                "new_users_week": stats.get("new_users_week", 0),
                "new_users_month": stats.get("new_users_month", 0),
                "total_requests": total_requests,
                "requests_today": stats.get("requests_today", 0),
                "requests_week": stats.get("requests_week", 0),
                "requests_month": stats.get("requests_month", 0),
                "total_broadcasts": stats.get("broadcasts_total", 0),
                "completed_broadcasts": stats.get("broadcasts_completed", 0),
                "conversion_rate": conversion_rate,
                "avg_requests_per_user": avg_requests_per_user,
                "broadcast_success_rate": broadcast_success_rate
            },
            "charts": {
                "user_growth": chart_data["user_growth"],
                "request_activity": chart_data["request_activity"],
                "daily_stats": chart_data["daily_stats"]
            },
            "top_users": stats.get("top_users", []),
            "recent_activity": await get_recent_activity(db),
            "system_health": await get_system_health(db),
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики dashboard: {e}")
        # Возвращаем пустую статистику при ошибке
        return {
            "summary": {
                "total_users": 0,
                "active_subscriptions": 0,
                "search_requests": 0,
                "monthly_revenue": 0,
                "today_users": 0,
                "today_searches": 0,
                "today_subscriptions": 0,
                "today_revenue": 0,
                "conversion_rate": 0.0,
                "avg_requests_per_user": 0.0,
                "broadcast_success_rate": 0.0
            },
            "charts": {
                "user_growth": [],
                "request_activity": [],
                "daily_stats": []
            },
            "top_users": [],
            "recent_activity": [],
            "system_health": {"status": "error", "error": str(e)},
            "generated_at": datetime.now().isoformat()
        }


def process_activity_data(activity_data: List[Dict]) -> Dict[str, Any]:
    """Обработать данные активности для графиков"""

    # Группируем данные по датам
    daily_data = {}
    for item in activity_data:
        date = item["date"]
        if date not in daily_data:
            daily_data[date] = {"new_users": 0, "requests": 0}

        daily_data[date]["new_users"] += item.get("new_users", 0)
        daily_data[date]["requests"] += item.get("requests_count", 0)

    # Сортируем по датам и создаем массивы для графиков
    sorted_dates = sorted(daily_data.keys())

    user_growth = []
    request_activity = []
    daily_stats = []

    for date in sorted_dates:
        data = daily_data[date]
        user_growth.append({
            "date": date,
            "value": data["new_users"]
        })
        request_activity.append({
            "date": date,
            "value": data["requests"]
        })
        daily_stats.append({
            "date": date,
            "new_users": data["new_users"],
            "requests": data["requests"]
        })

    return {
        "user_growth": user_growth,
        "request_activity": request_activity,
        "daily_stats": daily_stats
    }


async def get_recent_activity(db: UniversalDatabase) -> List[Dict[str, Any]]:
    """Получить последние действия в системе"""
    try:
        # Получаем последние логи действий
        logs_result = await db.get_audit_logs(page=1, per_page=10)

        recent_activity = []
        for log in logs_result["logs"]:
            recent_activity.append({
                "id": log["id"],
                "action": log["action"],
                "resource_type": log["resource_type"],
                "username": log.get("username", "Unknown"),
                "created_at": log["created_at"],
                "details": log.get("details")
            })

        return recent_activity
    except Exception:
        return []


async def get_system_health(db: UniversalDatabase) -> Dict[str, Any]:
    """Получить информацию о состоянии системы"""
    try:
        import os
        import psutil

        # Информация о системе
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Размер базы данных
        db_size = 0
        try:
            db_size = os.path.getsize(db.db_path)
        except:
            pass

        return {
            "status": "healthy",
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "memory_available": memory.available,
            "disk_usage": disk.percent,
            "disk_free": disk.free,
            "database_size": db_size,
            "uptime": "N/A"  # TODO: Реализовать отслеживание uptime
        }
    except ImportError:
        # psutil не установлен
        return {
            "status": "unknown",
            "message": "System monitoring unavailable (psutil not installed)"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
