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
from ..services.api_client import api_client

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
    """
    Production-ready обработка формы входа
    Поддерживает локальную и удаленную аутентификацию с fallback
    """

    # Логируем попытку входа для аудита
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    logger.info(f"🔐 Попытка входа: пользователь={username}, IP={client_ip}")

    try:
        # Используем production-ready API клиент
        token_data = await api_client.authenticate(username, password)

        # Определяем настройки безопасности для cookies
        is_production = os.getenv("ENVIRONMENT") == "production"
        secure_cookies = is_production

        # Создаем ответ с редиректом
        redirect_response = RedirectResponse(url="/dashboard", status_code=302)

        # Устанавливаем токены в cookies с правильными настройками безопасности
        redirect_response.set_cookie(
            key="access_token",
            value=token_data["access_token"],
            httponly=True,
            secure=secure_cookies,
            samesite="strict" if is_production else "lax",
            max_age=token_data.get("expires_in", 1800)
        )

        redirect_response.set_cookie(
            key="refresh_token",
            value=token_data["refresh_token"],
            httponly=True,
            secure=secure_cookies,
            samesite="strict" if is_production else "lax",
            max_age=7 * 24 * 60 * 60  # 7 дней
        )

        # Токен для JavaScript (с правильными настройками безопасности)
        redirect_response.set_cookie(
            key="js_access_token",
            value=token_data["access_token"],
            httponly=False,  # JavaScript должен иметь доступ
            secure=secure_cookies,  # HTTPS в production
            samesite="strict" if is_production else "lax",
            max_age=token_data.get("expires_in", 1800)
        )

        # Логируем успешный вход
        logger.info(f"✅ Успешный вход: пользователь={username}, IP={client_ip}")

        return redirect_response

    except HTTPException as e:
        # Обрабатываем HTTP ошибки от API клиента
        error_detail = e.detail
        status_code = e.status_code

        if status_code == 401:
            error_detail = "Неверное имя пользователя или пароль"
            logger.warning(f"⚠️ Неудачная попытка входа: пользователь={username}, IP={client_ip}")
        elif status_code == 503:
            error_detail = "Сервис временно недоступен. Попробуйте позже."
            logger.error(f"❌ Сервис недоступен при входе: пользователь={username}, IP={client_ip}")
        else:
            logger.error(f"❌ HTTP ошибка при входе: {status_code} - {error_detail}")

        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": error_detail,
                "username": username
            }
        )

    except Exception as e:
        # Обрабатываем неожиданные ошибки
        logger.error(f"❌ Неожиданная ошибка при аутентификации: {str(e)}", exc_info=True)

        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": "Произошла внутренняя ошибка. Попробуйте позже.",
                "username": username
            }
        )


@router.get("/logout")
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("js_access_token")
    response.delete_cookie("csrf_token")
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

        # Добавляем токен для JavaScript (без httponly)
        response.set_cookie(
            key="js_access_token",
            value=access_token,
            max_age=3600,  # 1 час
            httponly=False,  # JavaScript может читать
            secure=True if os.getenv('ENVIRONMENT') == 'production' else False,
            samesite="lax"
        )

        # Логируем успешный вход для аудита
        try:
            from database.universal_database import UniversalDatabase
            db = UniversalDatabase()
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
