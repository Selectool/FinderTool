"""
API endpoints для управления пользователями
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, BackgroundTasks
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio

from ..auth.permissions import (
    RequireUserView, RequireUserEdit, get_current_active_user,
    log_admin_action
)
from ..models.user_models import (
    UserResponse, UsersListResponse, UserUpdateRequest,
    SubscriptionUpdateRequest, UserStatsResponse, BulkActionRequest,
    UserExportRequest, UserSearchRequest, UserFilterType,
    UserNotificationRequest, UserAnalyticsResponse
)
from database.universal_database import UniversalDatabase

router = APIRouter()


async def get_db(request: Request) -> UniversalDatabase:
    """Получить объект базы данных"""
    return request.state.db


@router.get("/", response_model=UsersListResponse)
@log_admin_action("view_users", "users")
async def get_users(
    page: int = Query(1, ge=1, description="Номер страницы"),
    per_page: int = Query(50, ge=1, le=200, description="Количество на странице"),
    search: Optional[str] = Query(None, max_length=100, description="Поиск по имени/username/ID"),
    filter_type: Optional[UserFilterType] = Query(None, description="Тип фильтра"),
    sort_by: str = Query("created_at", pattern="^(created_at|requests_used|last_request|username)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user = Depends(RequireUserView),
    db: UniversalDatabase = Depends(get_db)
):
    """Получить список пользователей с фильтрацией и пагинацией"""

    # Преобразуем filter_type в строку для совместимости с UniversalDatabase
    filter_str = None
    if filter_type:
        if filter_type == UserFilterType.subscribed:
            filter_str = "subscribed"
        elif filter_type == UserFilterType.unlimited:
            filter_str = "unlimited"
        elif filter_type == UserFilterType.blocked:
            filter_str = "blocked"
        elif filter_type == UserFilterType.bot_blocked:
            filter_str = "bot_blocked"
        elif filter_type == UserFilterType.active:
            filter_str = "active"

    # Получаем пользователей из базы данных
    result = await db.get_users_paginated(
        page=page,
        per_page=per_page,
        search=search,
        filter_type=filter_str
    )

    # Преобразуем в модели Pydantic
    users = []
    for user_data in result["users"]:
        user = UserResponse(**user_data)
        users.append(user)

    return UsersListResponse(
        users=users,
        total=result["total"],
        page=result["page"],
        per_page=result["per_page"],
        pages=result["pages"],
        filters_applied={
            "search": search,
            "filter_type": filter_type.value if filter_type else None,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
    )


@router.get("/{user_id}", response_model=UserResponse)
@log_admin_action("view_user", "users")
async def get_user(
    user_id: int,
    current_user = Depends(RequireUserView),
    db: UniversalDatabase = Depends(get_db)
):
    """Получить информацию о конкретном пользователе"""
    user_data = await db.get_user(user_id)

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    return UserResponse(**user_data)


@router.delete("/{user_id}")
@log_admin_action("delete_user", "users")
async def delete_user(
    user_id: int,
    current_user = Depends(RequireUserEdit),
    db: UniversalDatabase = Depends(get_db)
):
    """Удалить пользователя"""
    # Проверяем существование пользователя
    user_data = await db.get_user(user_id)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Удаляем пользователя
    success = await db.delete_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при удалении пользователя"
        )

    return {"message": "Пользователь успешно удален", "user_id": user_id}


@router.put("/{user_id}", response_model=UserResponse)
@log_admin_action("update_user", "users")
async def update_user(
    user_id: int,
    update_data: UserUpdateRequest,
    current_user = Depends(RequireUserEdit),
    db: UniversalDatabase = Depends(get_db)
):
    """Обновить информацию о пользователе"""
    # Проверяем существование пользователя
    user_data = await db.get_user(user_id)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Обновляем пользователя
    success = await db.update_user_permissions(
        user_id=user_id,
        unlimited_access=update_data.unlimited_access,
        blocked=update_data.blocked,
        notes=update_data.notes
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось обновить пользователя"
        )

    # Возвращаем обновленные данные
    updated_user = await db.get_user(user_id)
    return UserResponse(**updated_user)


@router.post("/{user_id}/subscription")
@log_admin_action("update_subscription", "users")
async def update_user_subscription(
    user_id: int,
    subscription_data: SubscriptionUpdateRequest,
    current_user = Depends(RequireUserEdit),
    db: UniversalDatabase = Depends(get_db)
):
    """Управление подпиской пользователя"""
    # Проверяем существование пользователя
    user_data = await db.get_user(user_id)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    if subscription_data.action == "activate":
        await db.subscribe_user(user_id, subscription_data.months)
        message = f"Подписка активирована на {subscription_data.months} мес."

    elif subscription_data.action == "extend":
        # Продлеваем существующую подписку
        current_end = user_data.get("subscription_end")
        if current_end and datetime.fromisoformat(current_end) > datetime.now():
            # Продлеваем от текущей даты окончания
            base_date = datetime.fromisoformat(current_end)
        else:
            # Продлеваем от текущей даты
            base_date = datetime.now()

        new_end = base_date + timedelta(days=30 * subscription_data.months)

        import aiosqlite
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute("""
                UPDATE users
                SET is_subscribed = TRUE, subscription_end = ?
                WHERE user_id = ?
            """, (new_end, user_id))
            await conn.commit()

        message = f"Подписка продлена на {subscription_data.months} мес."

    elif subscription_data.action == "deactivate":
        import aiosqlite
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute("""
                UPDATE users
                SET is_subscribed = FALSE, subscription_end = NULL
                WHERE user_id = ?
            """, (user_id,))
            await conn.commit()

        message = "Подписка деактивирована"

    return {"message": message, "user_id": user_id}


@router.get("/{user_id}/stats", response_model=UserStatsResponse)
@log_admin_action("view_user_stats", "users")
async def get_user_stats(
    user_id: int,
    current_user = Depends(RequireUserView),
    db: UniversalDatabase = Depends(get_db)
):
    """Получить статистику пользователя"""
    # Проверяем существование пользователя
    user_data = await db.get_user(user_id)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Получаем статистику запросов
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Общее количество запросов
        cursor = await conn.execute(
            "SELECT COUNT(*) as total FROM requests WHERE user_id = ?",
            (user_id,)
        )
        total_requests = (await cursor.fetchone())["total"]

        # Запросы за сегодня
        cursor = await conn.execute("""
            SELECT COUNT(*) as today FROM requests
            WHERE user_id = ? AND DATE(created_at) = DATE('now')
        """, (user_id,))
        requests_today = (await cursor.fetchone())["today"]

        # Запросы за неделю
        cursor = await conn.execute("""
            SELECT COUNT(*) as week FROM requests
            WHERE user_id = ? AND DATE(created_at) >= DATE('now', '-7 days')
        """, (user_id,))
        requests_week = (await cursor.fetchone())["week"]

        # Запросы за месяц
        cursor = await conn.execute("""
            SELECT COUNT(*) as month FROM requests
            WHERE user_id = ? AND DATE(created_at) >= DATE('now', '-30 days')
        """, (user_id,))
        requests_month = (await cursor.fetchone())["month"]

        # Первый и последний запрос
        cursor = await conn.execute("""
            SELECT MIN(created_at) as first_request, MAX(created_at) as last_request
            FROM requests WHERE user_id = ?
        """, (user_id,))
        request_dates = await cursor.fetchone()

    return UserStatsResponse(
        user_id=user_id,
        total_requests=total_requests,
        requests_today=requests_today,
        requests_week=requests_week,
        requests_month=requests_month,
        first_request=request_dates["first_request"],
        last_request=request_dates["last_request"],
        favorite_channels=[],  # TODO: Реализовать анализ популярных каналов
        subscription_history=[]  # TODO: Реализовать историю подписок
    )


@router.post("/bulk-action")
@log_admin_action("bulk_action", "users")
async def bulk_user_action(
    action_data: BulkActionRequest,
    current_user = Depends(RequireUserEdit),
    db: UniversalDatabase = Depends(get_db)
):
    """Массовые действия с пользователями"""
    results = {"success": [], "failed": []}

    for user_id in action_data.user_ids:
        try:
            if action_data.action == "block":
                success = await db.update_user_permissions(
                    user_id=user_id,
                    blocked=True,
                    notes=action_data.notes
                )
            elif action_data.action == "unblock":
                success = await db.update_user_permissions(
                    user_id=user_id,
                    blocked=False,
                    notes=action_data.notes
                )
            elif action_data.action == "grant_unlimited":
                success = await db.update_user_permissions(
                    user_id=user_id,
                    unlimited_access=True,
                    notes=action_data.notes
                )
            elif action_data.action == "revoke_unlimited":
                success = await db.update_user_permissions(
                    user_id=user_id,
                    unlimited_access=False,
                    notes=action_data.notes
                )
            elif action_data.action == "delete":
                success = await db.delete_user(user_id)
            else:
                success = False

            if success:
                results["success"].append(user_id)
            else:
                results["failed"].append(user_id)

        except Exception as e:
            results["failed"].append(user_id)

    return {
        "message": f"Обработано {len(action_data.user_ids)} пользователей",
        "results": results,
        "action": action_data.action
    }


@router.get("/search/", response_model=List[UserResponse])
@log_admin_action("search_users", "users")
async def search_users(
    query: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    current_user = Depends(RequireUserView),
    db: UniversalDatabase = Depends(get_db)
):
    """Поиск пользователей"""
    result = await db.get_users_paginated(
        page=1,
        per_page=limit,
        search=query
    )

    users = [UserResponse(**user_data) for user_data in result["users"]]
    return users


@router.get("/analytics/", response_model=UserAnalyticsResponse)
@log_admin_action("view_user_analytics", "users")
async def get_user_analytics(
    current_user = Depends(RequireUserView),
    db: UniversalDatabase = Depends(get_db)
):
    """Получить аналитику пользователей"""
    stats = await db.get_detailed_stats()
    user_stats = stats["users"]

    # Вычисляем сегменты
    total = user_stats["total_users"]
    segments = []

    if total > 0:
        segments = [
            {
                "segment_name": "Активные подписчики",
                "count": user_stats["active_subscribers"],
                "percentage": round((user_stats["active_subscribers"] / total) * 100, 2),
                "description": "Пользователи с активной подпиской"
            },
            {
                "segment_name": "Безлимитные пользователи",
                "count": user_stats["unlimited_users"],
                "percentage": round((user_stats["unlimited_users"] / total) * 100, 2),
                "description": "Пользователи с безлимитным доступом"
            },
            {
                "segment_name": "Заблокированные",
                "count": user_stats["blocked_users"],
                "percentage": round((user_stats["blocked_users"] / total) * 100, 2),
                "description": "Заблокированные пользователи"
            },
            {
                "segment_name": "Новые за неделю",
                "count": user_stats["new_week"],
                "percentage": round((user_stats["new_week"] / total) * 100, 2),
                "description": "Зарегистрированы за последние 7 дней"
            }
        ]

    # Простой расчет роста (можно улучшить)
    growth_rate = 0.0
    if user_stats["new_month"] > 0 and total > user_stats["new_month"]:
        growth_rate = round((user_stats["new_month"] / (total - user_stats["new_month"])) * 100, 2)

    return UserAnalyticsResponse(
        total_users=total,
        active_users=user_stats["active_subscribers"] + user_stats["unlimited_users"],
        new_users_today=user_stats["new_today"],
        new_users_week=user_stats["new_week"],
        new_users_month=user_stats["new_month"],
        subscribers=user_stats["active_subscribers"],
        unlimited_users=user_stats["unlimited_users"],
        blocked_users=user_stats["blocked_users"],
        segments=segments,
        growth_rate=growth_rate,
        retention_rate=85.0  # TODO: Реализовать расчет retention rate
    )


@router.post("/export/")
@log_admin_action("export_users", "users")
async def export_users(
    export_data: UserExportRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(RequireUserView),
    db: UniversalDatabase = Depends(get_db)
):
    """Экспорт пользователей в CSV/Excel"""
    from fastapi.responses import StreamingResponse
    import io
    import csv

    # Получаем данные пользователей
    result = await db.get_users_paginated(
        page=1,
        per_page=10000,  # Большой лимит для экспорта
        search=export_data.search,
        filter_type=export_data.filter_type.value if export_data.filter_type else None
    )

    if export_data.format == "csv":
        # Создаем CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Заголовки
        headers = [
            "ID", "Username", "Имя", "Фамилия", "Дата регистрации",
            "Запросов использовано", "Подписка", "Дата окончания подписки",
            "Последний запрос", "Роль", "Безлимитный доступ", "Заблокирован", "Заметки"
        ]
        writer.writerow(headers)

        # Данные
        for user_data in result["users"]:
            user = UserResponse(**user_data)
            row = [
                user.user_id,
                user.username or "",
                user.first_name or "",
                user.last_name or "",
                user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "",
                user.requests_used,
                "Да" if user.is_subscribed else "Нет",
                user.subscription_end.strftime("%Y-%m-%d %H:%M:%S") if user.subscription_end else "",
                user.last_request.strftime("%Y-%m-%d %H:%M:%S") if user.last_request else "",
                user.role,
                "Да" if user.unlimited_access else "Нет",
                "Да" if user.blocked else "Нет",
                user.notes or ""
            ]
            writer.writerow(row)

        output.seek(0)

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )

    elif export_data.format == "xlsx":
        # Создаем Excel файл
        try:
            import openpyxl
            from openpyxl.utils import get_column_letter

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Пользователи"

            # Заголовки
            headers = [
                "ID", "Username", "Имя", "Фамилия", "Дата регистрации",
                "Запросов использовано", "Подписка", "Дата окончания подписки",
                "Последний запрос", "Роль", "Безлимитный доступ", "Заблокирован", "Заметки"
            ]

            for col, header in enumerate(headers, 1):
                ws.cell(row=1, column=col, value=header)

            # Данные
            for row_num, user_data in enumerate(result["users"], 2):
                user = UserResponse(**user_data)
                data = [
                    user.user_id,
                    user.username or "",
                    user.first_name or "",
                    user.last_name or "",
                    user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "",
                    user.requests_used,
                    "Да" if user.is_subscribed else "Нет",
                    user.subscription_end.strftime("%Y-%m-%d %H:%M:%S") if user.subscription_end else "",
                    user.last_request.strftime("%Y-%m-%d %H:%M:%S") if user.last_request else "",
                    user.role,
                    "Да" if user.unlimited_access else "Нет",
                    "Да" if user.blocked else "Нет",
                    user.notes or ""
                ]

                for col, value in enumerate(data, 1):
                    ws.cell(row=row_num, column=col, value=value)

            # Автоширина колонок
            for col in range(1, len(headers) + 1):
                ws.column_dimensions[get_column_letter(col)].auto_size = True

            # Сохраняем в память
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)

            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"}
            )

        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Библиотека openpyxl не установлена"
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неподдерживаемый формат экспорта"
        )
