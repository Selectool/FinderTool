"""
Веб-страницы аутентификации
"""
from fastapi import APIRouter, Request, Form, HTTPException, status, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import httpx
import logging

from ..auth.auth import verify_token
from ..auth.models import TokenData

templates = Jinja2Templates(directory="admin/templates")
router = APIRouter()
logger = logging.getLogger(__name__)


async def get_current_user_from_cookie(access_token: Optional[str] = Cookie(None)) -> Optional[TokenData]:
    """Получить текущего пользователя из cookie"""
    if not access_token:
        return None

    token_data = verify_token(access_token)
    return token_data


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user: Optional[TokenData] = Depends(get_current_user_from_cookie)
):
    """Страница входа в систему"""
    # Если пользователь уже авторизован, перенаправляем на dashboard
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Обработка формы входа"""
    try:
        # Отправляем запрос к API аутентификации
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:8080/api/auth/login",
                json={"username": username, "password": password},
                timeout=10.0
            )

        if response.status_code == 200:
            token_data = response.json()

            # Создаем ответ с редиректом
            redirect_response = RedirectResponse(url="/dashboard", status_code=302)

            # Устанавливаем токены в cookies
            redirect_response.set_cookie(
                key="access_token",
                value=token_data["access_token"],
                httponly=True,
                secure=False,  # В production должно быть True
                samesite="lax",
                max_age=token_data.get("expires_in", 1800)  # 30 минут по умолчанию
            )
            redirect_response.set_cookie(
                key="refresh_token",
                value=token_data["refresh_token"],
                httponly=True,
                secure=False,
                samesite="lax",
                max_age=7 * 24 * 60 * 60  # 7 дней
            )

            logger.info(f"Успешный вход пользователя: {username}")

            return redirect_response

        else:
            error_detail = "Неверное имя пользователя или пароль"
            if response.status_code == 422:
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", error_detail)
                except:
                    pass

            logger.warning(f"Неудачная попытка входа: {username}")
            return templates.TemplateResponse(
                "auth/login.html",
                {
                    "request": request,
                    "error": error_detail,
                    "username": username  # Сохраняем введенное имя пользователя
                }
            )

    except httpx.TimeoutException:
        logger.error("Timeout при попытке аутентификации")
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": "Превышено время ожидания. Попробуйте еще раз.",
                "username": username
            }
        )
    except Exception as e:
        logger.error(f"Ошибка при аутентификации: {str(e)}")
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": "Ошибка подключения к серверу. Попробуйте позже.",
                "username": username
            }
        )


@router.get("/logout")
async def logout(request: Request):
    """Выход из системы"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response
