"""
Веб-страница дашборда
"""
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from ..web.auth import get_current_user_from_cookie
from ..auth.models import TokenData

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
    current_user: TokenData = Depends(require_auth)
):
    """Главная страница админ-панели"""
    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "current_user": current_user,
            "page_title": "Dashboard"
        }
    )
