"""
Веб-страницы аутентификации
"""
from fastapi import APIRouter, Request, Form, HTTPException, status, Depends, Cookie, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import httpx
import logging
import os
from datetime import datetime

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
                f"http://185.207.66.201:8080/api/auth/login",
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
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response

@router.get("/token-login")
async def token_login(token: str = Query(...), request: Request = None):
    """
    Secure автологин через временный токен из Telegram бота
    Production-ready endpoint с полной валидацией
    """
    try:
        # Импортируем менеджер токенов из бота
        from bot.handlers.admin_access import token_manager
        from admin.security.production_auth import security_manager

        logger.info(f"🔐 Попытка token login с токеном: {token[:20]}...")

        # Проверяем временный токен из бота
        temp_payload = token_manager.verify_token(token)

        if not temp_payload:
            logger.warning("⚠️ Недействительный временный токен")
            return HTMLResponse(
                content="""
                <html>
                    <head><title>Ошибка доступа</title></head>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h1>🚫 Доступ запрещен</h1>
                        <p>Недействительный или истекший токен доступа.</p>
                        <p>Получите новый токен через команду /admin в боте.</p>
                        <a href="https://t.me/FinderTool_bot">🤖 Перейти к боту</a>
                    </body>
                </html>
                """,
                status_code=403
            )

        user_id = temp_payload.get('user_id')
        username = temp_payload.get('username')

        logger.info(f"✅ Временный токен валиден для пользователя {user_id} (@{username})")

        # Проверяем права администратора
        admin_ids = [int(id.strip()) for id in os.getenv('ADMIN_USER_IDS', '').split(",") if id.strip()]

        if user_id not in admin_ids:
            logger.warning(f"⚠️ Пользователь {user_id} не является администратором")
            return HTMLResponse(
                content="""
                <html>
                    <head><title>Недостаточно прав</title></head>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h1>⚠️ Недостаточно прав</h1>
                        <p>У вас нет прав администратора для доступа к панели.</p>
                        <a href="https://t.me/FinderTool_bot">🤖 Вернуться к боту</a>
                    </body>
                </html>
                """,
                status_code=403
            )

        # Генерируем полноценный JWT токен для админ-панели
        access_token = security_manager.generate_jwt_token(user_id, "access")
        refresh_token = security_manager.generate_jwt_token(user_id, "refresh")

        # Генерируем CSRF токен
        csrf_token = security_manager.generate_csrf_token(user_id)

        # Отзываем временный токен (одноразовое использование)
        token_manager._remove_token(user_id, token)

        logger.info(f"🎉 Успешный автологин администратора {user_id} (@{username})")

        # Создаем response с редиректом на дашборд
        response = RedirectResponse(url="/dashboard", status_code=302)

        # Устанавливаем secure cookies
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=3600,  # 1 час
            httponly=True,
            secure=True if os.getenv('ENVIRONMENT') == 'production' else False,
            samesite="lax"
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=2592000,  # 30 дней
            httponly=True,
            secure=True if os.getenv('ENVIRONMENT') == 'production' else False,
            samesite="lax"
        )

        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            max_age=3600,  # 1 час
            httponly=False,  # Нужен для JavaScript
            secure=True if os.getenv('ENVIRONMENT') == 'production' else False,
            samesite="lax"
        )

        # Логируем успешный вход для аудита
        try:
            from database.models import Database
            db = Database()
            await db.log_admin_action(
                admin_id=user_id,
                action="secure_token_login",
                details={
                    "username": username,
                    "login_method": "telegram_token",
                    "ip_address": request.client.host if request and request.client else "unknown",
                    "user_agent": request.headers.get("user-agent") if request else "unknown",
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            logger.warning(f"Не удалось записать лог аудита: {e}")

        return response

    except Exception as e:
        logger.error(f"❌ Ошибка при token login: {e}")
        return HTMLResponse(
            content="""
            <html>
                <head><title>Ошибка сервера</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1>❌ Ошибка сервера</h1>
                    <p>Произошла внутренняя ошибка при обработке запроса.</p>
                    <p>Попробуйте получить новый токен через команду /admin в боте.</p>
                    <a href="https://t.me/FinderTool_bot">🤖 Перейти к боту</a>
                </body>
            </html>
            """,
            status_code=500
        )
