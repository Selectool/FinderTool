"""
Веб-страницы рассылок
"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from ..web.auth import get_current_user_from_cookie
from ..auth.models import TokenData
from database.universal_database import UniversalDatabase

templates = Jinja2Templates(directory="admin/templates")
router = APIRouter()


async def require_auth(current_user: Optional[TokenData] = Depends(get_current_user_from_cookie)):
    """Middleware для проверки аутентификации"""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)
    return current_user


async def get_db(request: Request) -> UniversalDatabase:
    """Получить объект базы данных"""
    return request.state.db


@router.get("/", response_class=HTMLResponse)
async def broadcasts_list(
    request: Request,
    page: int = 1,
    status: str = None,
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """Страница списка рассылок"""

    # Получаем список рассылок с пагинацией
    broadcasts_data = await db.get_broadcasts_paginated(page=page, per_page=20)

    # Получаем статистику рассылок
    broadcasts_stats = await db.get_broadcasts_stats()

    return templates.TemplateResponse(
        "broadcasts/list.html",
        {
            "request": request,
            "current_user": current_user,
            "broadcasts": broadcasts_data["broadcasts"],
            "pagination": broadcasts_data["pagination"],
            "broadcasts_stats": broadcasts_stats,
            "page_title": "Массовые рассылки"
        }
    )


@router.get("/create", response_class=HTMLResponse)
async def create_broadcast_page(
    request: Request,
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """Страница создания рассылки"""

    # Получаем шаблоны сообщений
    templates_list = await db.get_message_templates()

    return templates.TemplateResponse(
        "broadcasts/create.html",
        {
            "request": request,
            "current_user": current_user,
            "templates": templates_list,
            "page_title": "Создание рассылки"
        }
    )


@router.get("/{broadcast_id}", response_class=HTMLResponse)
async def broadcast_detail(
    request: Request,
    broadcast_id: int,
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """Страница детальной информации о рассылке"""

    # Получаем информацию о рассылке
    broadcast = await db.get_broadcast_by_id(broadcast_id)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    # Получаем детальную статистику рассылки
    stats = await db.get_broadcast_detailed_stats(broadcast_id)

    return templates.TemplateResponse(
        "broadcasts/detail.html",
        {
            "request": request,
            "current_user": current_user,
            "broadcast": broadcast,
            "stats": stats,
            "page_title": f"Рассылка #{broadcast_id}"
        }
    )


@router.get("/templates", response_class=HTMLResponse)
async def templates_list(
    request: Request,
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """Страница списка шаблонов сообщений"""

    # Получаем список шаблонов
    templates_list = await db.get_message_templates()

    return templates.TemplateResponse(
        "broadcasts/templates.html",
        {
            "request": request,
            "current_user": current_user,
            "templates": templates_list,
            "page_title": "Шаблоны сообщений"
        }
    )


@router.get("/templates/create", response_class=HTMLResponse)
async def create_template_page(
    request: Request,
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """Страница создания шаблона сообщения"""

    return templates.TemplateResponse(
        "broadcasts/template_create.html",
        {
            "request": request,
            "current_user": current_user,
            "page_title": "Создание шаблона"
        }
    )


@router.post("/templates/create")
async def create_template(
    request: Request,
    name: str = Form(...),
    content: str = Form(...),
    category: str = Form("general"),
    current_user: TokenData = Depends(require_auth),
    db: UniversalDatabase = Depends(get_db)
):
    """Создать шаблон сообщения"""

    template_id = await db.create_message_template(
        name=name,
        content=content,
        category=category,
        created_by=current_user.user_id
    )

    return RedirectResponse(url="/broadcasts/templates", status_code=302)
