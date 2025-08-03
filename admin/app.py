"""
Главное FastAPI приложение админ-панели
"""
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
import structlog

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .config import (
        DEBUG, HOST, PORT, CORS_ORIGINS, ALLOWED_HOSTS,
        LOG_LEVEL, UPLOAD_DIR
    )
except ImportError:
    from config import (
        DEBUG, HOST, PORT, CORS_ORIGINS, ALLOWED_HOSTS,
        LOG_LEVEL, UPLOAD_DIR
    )

# Импорты для админ-панели
try:
    from admin.auth.broadcast_permissions import init_broadcast_permissions, add_get_user_permissions_method
except ImportError:
    try:
        from .auth.broadcast_permissions import init_broadcast_permissions, add_get_user_permissions_method
    except ImportError:
        # Заглушка если модуль не найден
        async def init_broadcast_permissions(db):
            logger.warning("init_broadcast_permissions не найден, пропускаем")
            pass
        def add_get_user_permissions_method():
            logger.warning("add_get_user_permissions_method не найден, пропускаем")
            pass

# Настройка логирования
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Инициализация при запуске
    logger.info("Запуск админ-панели...")

    # Используем UniversalDatabase для совместимости с ботом
    try:
        from database.universal_database import UniversalDatabase
        from database.production_manager import db_manager

        # Инициализируем production manager для создания таблиц
        await db_manager.initialize_database()

        # Создаем UniversalDatabase для админ-панели
        db = UniversalDatabase(db_manager.database_url)

    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        raise

    # Инициализация системы прав доступа для рассылок
    await init_broadcast_permissions(db)

    # Инициализация сервиса аудита
    from admin.services.audit_service import init_audit_service
    init_audit_service(db)

    app.state.db = db

    logger.info("Админ-панель запущена успешно")
    
    yield
    
    # Очистка при завершении
    logger.info("Завершение работы админ-панели...")


# Создание приложения
app = FastAPI(
    title="Telegram Channel Finder Bot - Admin Panel",
    description="Админ-панель для управления ботом поиска каналов Telegram",
    version="1.0.0",
    debug=DEBUG,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ALLOWED_HOSTS != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=ALLOWED_HOSTS
    )


# Middleware для логирования запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Логирование HTTP запросов"""
    start_time = time.time()
    
    # Логируем входящий запрос
    logger.info(
        "HTTP request",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    response = await call_next(request)
    
    # Логируем ответ
    process_time = time.time() - start_time
    logger.info(
        "HTTP response",
        status_code=response.status_code,
        process_time=round(process_time, 4)
    )
    
    return response


# Middleware для добавления базы данных в request
@app.middleware("http")
async def add_db_to_request(request: Request, call_next):
    """Добавление объекта базы данных в request"""
    request.state.db = app.state.db
    response = await call_next(request)
    return response


# Статические файлы и шаблоны
# Определяем корневую директорию проекта
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
admin_dir = os.path.join(project_root, "admin")

static_dir = os.path.join(admin_dir, "static")
templates_dir = os.path.join(admin_dir, "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

templates = Jinja2Templates(directory=templates_dir)


# Обработчики ошибок
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Обработчик 404 ошибки"""
    return templates.TemplateResponse(
        "errors/404.html",
        {"request": request, "detail": "Страница не найдена"},
        status_code=404
    )


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc: HTTPException):
    """Обработчик 403 ошибки"""
    return templates.TemplateResponse(
        "errors/403.html",
        {"request": request, "detail": "Доступ запрещен"},
        status_code=403
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    """Обработчик 500 ошибки"""
    logger.error("Internal server error", exc_info=exc)
    return templates.TemplateResponse(
        "errors/500.html",
        {"request": request, "detail": "Внутренняя ошибка сервера"},
        status_code=500
    )


# Главная страница (редирект на логин или дашборд)
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/audit", response_class=HTMLResponse)
async def audit_logs_page(request: Request):
    """Страница логов аудита"""
    return templates.TemplateResponse("audit/logs.html", {"request": request})


# Подключение роутеров
try:
    from .api import auth, users, broadcasts, statistics, templates as template_routes, roles, audit, yookassa_webhook, payment_cleanup
except ImportError:
    from admin.api import auth, users, broadcasts, statistics, templates as template_routes, roles, audit, yookassa_webhook, payment_cleanup

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(broadcasts.router, prefix="/api/broadcasts", tags=["broadcasts"])
app.include_router(statistics.router, prefix="/api/statistics", tags=["statistics"])
app.include_router(template_routes.router, prefix="/api/templates", tags=["templates"])
app.include_router(roles.router, prefix="/api/roles", tags=["roles"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(yookassa_webhook.router, prefix="/api", tags=["yookassa-webhook"])
app.include_router(payment_cleanup.router, tags=["payment-cleanup"])

# Веб-страницы
try:
    from .web import auth as web_auth, dashboard, users as web_users, broadcasts as web_broadcasts, payment_cleanup as web_payment_cleanup
except ImportError:
    from admin.web import auth as web_auth, dashboard, users as web_users, broadcasts as web_broadcasts, payment_cleanup as web_payment_cleanup

# Добавляем метод get_user_permissions в класс UniversalDatabase
add_get_user_permissions_method()

app.include_router(web_auth.router, prefix="/auth", tags=["web-auth"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["web-dashboard"])
app.include_router(web_users.router, prefix="/users", tags=["web-users"])
app.include_router(web_broadcasts.router, prefix="/broadcasts", tags=["web-broadcasts"])
app.include_router(web_payment_cleanup.router, prefix="/payment-cleanup", tags=["web-payment-cleanup"])


# Информация о приложении
@app.get("/api/info")
async def app_info():
    """Информация о приложении"""
    return {
        "name": "Telegram Channel Finder Bot Admin Panel",
        "version": "1.0.0",
        "status": "running",
        "debug": DEBUG
    }


# Проверка здоровья приложения
@app.get("/api/health")
async def health_check(request: Request):
    """Проверка здоровья приложения"""
    try:
        # Проверяем подключение к базе данных
        db = request.state.db
        stats = await db.get_stats()
        
        return {
            "status": "healthy",
            "database": "connected",
            "users_count": stats.get("total_users", 0)
        }
    except Exception as e:
        logger.error("Health check failed", exc_info=e)
        return {
            "status": "unhealthy",
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    import time
    
    uvicorn.run(
        "admin.app:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level=LOG_LEVEL.lower()
    )
