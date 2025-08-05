"""
Веб-роутер для управления очисткой платежей
"""

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from admin.auth import require_admin
from database.db_adapter import get_database

router = APIRouter()

# Инициализация шаблонов
import os
admin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates_dir = os.path.join(admin_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

@router.get("/payment-cleanup", response_class=HTMLResponse)
async def payment_cleanup_page(
    request: Request,
    db=Depends(get_database),
    _=Depends(require_admin)
):
    """Страница управления очисткой платежей"""
    return templates.TemplateResponse(
        "payment_cleanup.html",
        {
            "request": request,
            "title": "Управление очисткой платежей",
            "page": "payment_cleanup"
        }
    )
