#!/usr/bin/env python3
"""
Production-Ready Telegram Channel Finder Bot
Единый процесс для Telegram бота + FastAPI админ-панели
Оптимизировано для Railpack и Dokploy деплоя
"""

import asyncio
import logging
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Telegram Bot imports
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# Project imports
from config import (
    BOT_TOKEN, DATABASE_URL, ENVIRONMENT, 
    ADMIN_HOST, ADMIN_PORT, SECRET_KEY
)
from database.production_manager import ProductionDatabaseManager
from database.models import Database
from bot.handlers.register import register_handlers
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from services.payment_cleanup import PaymentCleanupService
from utils.logging_config import setup_production_logging

# Setup logging
logger = setup_production_logging()

class ProductionApp:
    """Production-ready приложение"""
    
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.db: Optional[Database] = None
        self.cleanup_service: Optional[PaymentCleanupService] = None
        self.bot_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.running = False
        
        # FastAPI app будет создан в lifespan
        self.fastapi_app: Optional[FastAPI] = None

    async def initialize_database(self):
        """Инициализация PostgreSQL базы данных с миграциями"""
        logger.info("🔧 Инициализация production PostgreSQL базы данных...")
        
        try:
            # Production database manager
            db_manager = ProductionDatabaseManager()
            
            # Проверяем подключение к PostgreSQL
            await db_manager.verify_connection()
            logger.info("✅ Подключение к PostgreSQL установлено")
            
            # Выполняем миграции безопасно (без потери данных)
            await db_manager.run_safe_migrations()
            logger.info("✅ Миграции выполнены успешно")
            
            # Инициализируем Database объект
            self.db = Database()
            await self.db.create_tables_if_not_exist()
            
            # Оптимизируем для production
            await db_manager.optimize_for_production()
            
            logger.info("✅ База данных готова к работе")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            raise

    async def initialize_telegram_bot(self):
        """Инициализация Telegram бота"""
        logger.info("🤖 Инициализация Telegram бота...")
        
        try:
            # Создаем бота
            self.bot = Bot(
                token=BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            
            # Создаем диспетчер
            self.dp = Dispatcher(storage=MemoryStorage())
            
            # Регистрируем middleware
            self.dp.message.middleware(AuthMiddleware())
            self.dp.callback_query.middleware(AuthMiddleware())
            self.dp.message.middleware(ThrottlingMiddleware())
            self.dp.callback_query.middleware(ThrottlingMiddleware())
            
            # Регистрируем обработчики
            register_handlers(self.dp)
            
            # Получаем информацию о боте
            bot_info = await self.bot.get_me()
            logger.info(f"✅ Telegram бот инициализирован: @{bot_info.username}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Telegram бота: {e}")
            raise

    async def start_telegram_bot(self):
        """Запуск Telegram бота в background task"""
        logger.info("🚀 Запуск Telegram бота...")
        
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"❌ Ошибка в работе Telegram бота: {e}")
            raise

    async def initialize_cleanup_service(self):
        """Инициализация сервиса очистки платежей"""
        logger.info("🧹 Инициализация сервиса очистки платежей...")
        
        try:
            self.cleanup_service = PaymentCleanupService(self.db)
            logger.info("✅ Сервис очистки платежей инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации сервиса очистки: {e}")
            raise

    async def start_cleanup_service(self):
        """Запуск сервиса очистки в background"""
        if self.cleanup_service:
            try:
                await self.cleanup_service.start_cleanup_scheduler()
            except Exception as e:
                logger.error(f"❌ Ошибка в сервисе очистки: {e}")

    async def startup(self):
        """Инициализация всех сервисов"""
        logger.info("🚀 Запуск Production приложения...")
        logger.info(f"📍 Окружение: {ENVIRONMENT}")
        logger.info(f"🗄️ База данных: PostgreSQL")
        
        try:
            # Инициализируем базу данных
            await self.initialize_database()
            
            # Инициализируем Telegram бота
            await self.initialize_telegram_bot()
            
            # Инициализируем сервис очистки
            await self.initialize_cleanup_service()
            
            # Запускаем background задачи
            self.bot_task = asyncio.create_task(self.start_telegram_bot())
            self.cleanup_task = asyncio.create_task(self.start_cleanup_service())
            
            self.running = True
            
            logger.info("✅ Все сервисы запущены успешно!")
            logger.info(f"🤖 Telegram бот: Активен")
            logger.info(f"🌐 Админ-панель: http://{ADMIN_HOST}:{ADMIN_PORT}")
            logger.info(f"🧹 Очистка платежей: Активна")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске приложения: {e}")
            await self.shutdown()
            raise

    async def shutdown(self):
        """Корректное завершение работы"""
        logger.info("🛑 Завершение работы приложения...")
        
        self.running = False
        
        # Останавливаем background задачи
        if self.bot_task and not self.bot_task.done():
            self.bot_task.cancel()
            try:
                await self.bot_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Закрываем Telegram бота
        if self.bot:
            await self.bot.session.close()
        
        # Останавливаем сервис очистки
        if self.cleanup_service:
            self.cleanup_service.stop_cleanup_scheduler()
        
        logger.info("✅ Приложение корректно завершено")

# Глобальный экземпляр приложения
app_instance = ProductionApp()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом FastAPI приложения"""
    # Startup
    await app_instance.startup()
    
    yield
    
    # Shutdown
    await app_instance.shutdown()

# Создаем FastAPI приложение
app = FastAPI(
    title="Telegram Channel Finder Bot Admin Panel",
    description="Production-ready админ-панель для Telegram бота",
    version="1.0.0",
    lifespan=lifespan
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"] if ENVIRONMENT == "development" else [ADMIN_HOST, "localhost"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ENVIRONMENT == "development" else [f"http://{ADMIN_HOST}:{ADMIN_PORT}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="admin/static"), name="static")
templates = Jinja2Templates(directory="admin/templates")

# Подключаем роутеры админ-панели
from admin.api import (
    auth, users, statistics, broadcasts, 
    templates as template_routes, roles, 
    audit, yookassa_webhook, payment_cleanup
)
from admin.web import (
    auth as web_auth, dashboard, 
    users as web_users, broadcasts as web_broadcasts,
    payment_cleanup as web_payment_cleanup
)

# API роутеры
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(broadcasts.router, prefix="/api/broadcasts", tags=["broadcasts"])
app.include_router(statistics.router, prefix="/api/statistics", tags=["statistics"])
app.include_router(template_routes.router, prefix="/api/templates", tags=["templates"])
app.include_router(roles.router, prefix="/api/roles", tags=["roles"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(yookassa_webhook.router, prefix="/api", tags=["yookassa-webhook"])
app.include_router(payment_cleanup.router, tags=["payment-cleanup"])

# Web роутеры
app.include_router(web_auth.router, prefix="/auth", tags=["web-auth"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["web-dashboard"])
app.include_router(web_users.router, prefix="/users", tags=["web-users"])
app.include_router(web_broadcasts.router, prefix="/broadcasts", tags=["web-broadcasts"])
app.include_router(web_payment_cleanup.router, prefix="/admin", tags=["web-payment-cleanup"])

# Health check endpoint для Railpack/Dokploy
@app.get("/health")
async def health_check():
    """Health check для мониторинга"""
    try:
        # Проверяем состояние всех сервисов
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "services": {
                "telegram_bot": app_instance.running and app_instance.bot is not None,
                "database": app_instance.db is not None,
                "cleanup_service": app_instance.cleanup_service is not None,
                "admin_panel": True
            }
        }
        
        # Если какой-то сервис не работает, возвращаем unhealthy
        if not all(health_status["services"].values()):
            health_status["status"] = "unhealthy"
            return health_status, 503
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }, 503

# Metrics endpoint для мониторинга
@app.get("/metrics")
async def metrics():
    """Метрики для мониторинга"""
    try:
        if not app_instance.db:
            return {"error": "Database not initialized"}, 503
            
        stats = await app_instance.db.get_bot_stats()
        
        return {
            "telegram_bot": {
                "total_users": stats.get("total_users", 0),
                "active_subscribers": stats.get("active_subscribers", 0),
                "requests_today": stats.get("requests_today", 0)
            },
            "system": {
                "uptime": time.time() - (app_instance.startup_time if hasattr(app_instance, 'startup_time') else time.time()),
                "environment": ENVIRONMENT
            }
        }
        
    except Exception as e:
        logger.error(f"Metrics failed: {e}")
        return {"error": str(e)}, 503

# Главная страница - редирект на админ-панель
@app.get("/")
async def root():
    """Главная страница"""
    return {"message": "Telegram Channel Finder Bot API", "admin_panel": "/dashboard"}

if __name__ == "__main__":
    # Проверяем обязательные переменные окружения
    required_vars = ["BOT_TOKEN", "DATABASE_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
        sys.exit(1)
    
    # Запускаем приложение
    logger.info("🚀 Запуск Production сервера...")
    
    uvicorn.run(
        "app:app",
        host=ADMIN_HOST,
        port=ADMIN_PORT,
        reload=False,  # Отключаем reload в production
        access_log=ENVIRONMENT == "development",
        log_level="info"
    )
