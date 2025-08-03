"""
Веб-страницы пользователей
"""
from fastapi import APIRouter, Request, Depends, Query, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from datetime import datetime
import logging

from ..web.auth import get_current_user_from_cookie
from ..auth.models import TokenData
from database.universal_database import UniversalDatabase

templates = Jinja2Templates(directory="admin/templates")
router = APIRouter()
logger = logging.getLogger(__name__)


async def require_auth(current_user: Optional[TokenData] = Depends(get_current_user_from_cookie)):
    """Middleware для проверки аутентификации"""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
    return current_user


async def get_db(request: Request) -> UniversalDatabase:
    """Получить объект базы данных"""
    return request.state.db


def parse_datetime_field(date_str) -> datetime:
    """Преобразовать строку даты в объект datetime"""
    if not date_str:
        return None

    # Если уже datetime объект, возвращаем как есть
    if isinstance(date_str, datetime):
        return date_str

    try:
        # Преобразуем в строку если это не строка
        date_str = str(date_str)

        # Пробуем разные форматы
        formats = [
            '%Y-%m-%d %H:%M:%S.%f',  # С микросекундами
            '%Y-%m-%d %H:%M:%S',     # Без микросекунд
            '%Y-%m-%dT%H:%M:%S.%f',  # ISO формат с микросекундами
            '%Y-%m-%dT%H:%M:%S',     # ISO формат без микросекунд
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Если ничего не подошло, пробуем fromisoformat
        cleaned_str = str(date_str).replace('T', ' ').replace('Z', '')
        return datetime.fromisoformat(cleaned_str)

    except (ValueError, AttributeError, TypeError) as e:
        logger.warning(f"Не удалось преобразовать дату '{date_str}': {e}")
        return None


def process_user_dates(user: dict) -> dict:
    """Обработать даты пользователя для корректного отображения"""
    user_copy = user.copy()

    # Обрабатываем поля с датами
    date_fields = ['created_at', 'last_request', 'subscription_end']

    for field in date_fields:
        if field in user_copy and user_copy[field]:
            parsed_date = parse_datetime_field(user_copy[field])
            user_copy[field] = parsed_date

    return user_copy


@router.get("/", response_class=HTMLResponse)
async def users_list(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    filter_type: Optional[str] = Query(None),
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """Страница списка пользователей"""

    try:
        # Получаем пользователей с пагинацией
        result = await db.get_users_paginated(
            page=page,
            per_page=per_page,
            search=search,
            filter_type=filter_type
        )

        # Обрабатываем даты для корректного отображения
        processed_users = []
        for user in result["users"]:
            try:
                processed_user = process_user_dates(user)
                processed_users.append(processed_user)
            except Exception as e:
                logger.error(f"Ошибка обработки пользователя {user.get('user_id', 'unknown')}: {e}")
                # Добавляем пользователя без обработки дат
                processed_users.append(user)

        # Подготавливаем данные для пагинации
        total_pages = (result["total"] + per_page - 1) // per_page

    except Exception as e:
        logger.error(f"Ошибка получения списка пользователей: {e}")
        # Возвращаем пустой результат в случае ошибки
        processed_users = []
        total_pages = 0
        result = {"total": 0}

    return templates.TemplateResponse(
        "users/list.html",
        {
            "request": request,
            "current_user": current_user,
            "users": processed_users,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "per_page": per_page,
                "total_items": result["total"],
                "has_prev": page > 1,
                "has_next": page < total_pages,
                "prev_page": page - 1 if page > 1 else None,
                "next_page": page + 1 if page < total_pages else None
            },
            "filters": {
                "search": search,
                "filter_type": filter_type
            },
            "page_title": "Управление пользователями"
        }
    )


@router.get("/{user_id}", response_class=HTMLResponse)
async def user_detail(
    request: Request,
    user_id: int,
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """Страница детальной информации о пользователе"""

    # Получаем информацию о пользователе
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Обрабатываем даты пользователя
    processed_user = process_user_dates(user)

    # Получаем статистику пользователя (если метод существует)
    stats = {}
    try:
        stats = await db.get_user_stats(user_id)
    except AttributeError:
        # Если метод не существует, создаем базовую статистику
        stats = {
            'total_requests': user.get('requests_used', 0),
            'is_subscribed': user.get('is_subscribed', False),
            'unlimited_access': user.get('unlimited_access', False)
        }

    # Получаем историю запросов (если метод существует)
    requests_history = []
    try:
        requests_history = await db.get_user_requests(user_id, limit=10)
    except AttributeError:
        # Если метод не существует, оставляем пустой список
        pass

    return templates.TemplateResponse(
        "users/detail.html",
        {
            "request": request,
            "current_user": current_user,
            "user": processed_user,
            "stats": stats,
            "requests_history": requests_history,
            "page_title": f"Пользователь {user.get('username', user['user_id'])}"
        }
    )


@router.post("/{user_id}/block", response_class=HTMLResponse)
async def block_user(
    request: Request,
    user_id: int,
    notes: str = Form(""),
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """Заблокировать пользователя"""
    try:
        success = await db.update_user_permissions(
            user_id=user_id,
            blocked=True,
            notes=notes,
            blocked_by=current_user.user_id if hasattr(current_user, 'user_id') else None
        )

        if success:
            return RedirectResponse(url=f"/users/{user_id}", status_code=302)
        else:
            raise HTTPException(status_code=500, detail="Ошибка блокировки пользователя")

    except Exception as e:
        logger.error(f"Ошибка блокировки пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка блокировки пользователя")


@router.post("/{user_id}/unblock", response_class=HTMLResponse)
async def unblock_user(
    request: Request,
    user_id: int,
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """Разблокировать пользователя"""
    try:
        success = await db.update_user_permissions(
            user_id=user_id,
            blocked=False
        )

        if success:
            return RedirectResponse(url=f"/users/{user_id}", status_code=302)
        else:
            raise HTTPException(status_code=500, detail="Ошибка разблокировки пользователя")

    except Exception as e:
        logger.error(f"Ошибка разблокировки пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка разблокировки пользователя")


@router.post("/{user_id}/delete", response_class=HTMLResponse)
async def delete_user_web(
    request: Request,
    user_id: int,
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """Удалить пользователя"""
    try:
        success = await db.delete_user(user_id)

        if success:
            return RedirectResponse(url="/users/", status_code=302)
        else:
            raise HTTPException(status_code=500, detail="Ошибка удаления пользователя")

    except Exception as e:
        logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления пользователя")
