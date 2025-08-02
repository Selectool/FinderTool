#!/usr/bin/env python3
"""
Production-ready запуск Telegram Channel Finder Bot + Admin Panel
Единый процесс для бота и веб-админки
"""

import asyncio
import logging
import os
import sys
import signal
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
import uvicorn
from contextlib import asynccontextmanager

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импорты бота
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# Импорты админ-панели
from admin.main import app as admin_app

# Импорты конфигурации
from config import (
    BOT_TOKEN, ADMIN_HOST, ADMIN_PORT, ADMIN_DEBUG,
    ENVIRONMENT, DATABASE_TYPE
)

# Импорты модулей бота
from bot.handlers import register_handlers
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from database.db_adapter import Database
from database.production_manager import ProductionDatabaseManager
from database.admin_migrations import AdminMigrations
from database.reset_manager import DatabaseResetManager
from services.payment_cleanup import PaymentCleanupService, get_cleanup_service
from utils.logging_config import setup_logging

# Настройка логирования
logger = setup_logging()

class ProductionApp:
    """Production-ready приложение с ботом и админ-панелью"""
    
    def __init__(self):
        self.bot = None
        self.dp = None
        self.db = None
        self.admin_server = None
        self.cleanup_service = None
        self.cleanup_task = None
        self.running = False
        
    async def initialize_database(self):
        """Инициализация базы данных"""
        logger.info("🔧 Инициализация production-ready базы данных...")

        # Проверяем нужен ли сброс базы данных
        if os.getenv('RESET_DATABASE', 'false').lower() == 'true':
            logger.info("🔄 Выполняем сброс базы данных к чистому состоянию...")
            reset_manager = DatabaseResetManager()
            success = await reset_manager.reset_to_clean_state(keep_admin_users=True)
            if success:
                logger.info("✅ База данных сброшена к чистому состоянию")
            else:
                logger.error("❌ Ошибка при сбросе базы данных")
                raise Exception("Database reset failed")

        if DATABASE_TYPE == "postgresql":
            # Production PostgreSQL
            self.production_db = ProductionDatabaseManager()
            await self.production_db.optimize_for_production()
            logger.info("✅ PostgreSQL база данных инициализирована")
        else:
            # Fallback SQLite
            logger.warning("⚠️ Используется SQLite в production режиме")

        # Legacy Database для совместимости
        self.db = Database()
        await self.db.create_tables_if_not_exist()

        # Выполняем админ миграции
        migrations = AdminMigrations()
        await migrations.run_admin_migrations()

        # Инициализируем сервис очистки платежей
        self.cleanup_service = get_cleanup_service(self.db)

        logger.info("✅ База данных готова к работе")
    
    async def initialize_bot(self):
        """Инициализация Telegram бота"""
        logger.info("🤖 Инициализация Telegram бота...")
        
        # Создаем бота с правильными настройками
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
        logger.info(f"🤖 Бот запущен: @{bot_info.username} (ID: {bot_info.id})")
        
    async def start_bot(self):
        """Запуск бота в отдельной задаче"""
        logger.info("🚀 Запуск Telegram бота...")
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске бота: {e}")
            raise
    
    def start_admin_panel(self):
        """Запуск админ-панели в отдельном потоке"""
        logger.info(f"🌐 Запуск админ-панели на {ADMIN_HOST}:{ADMIN_PORT}")
        
        # Конфигурация uvicorn для production
        config = uvicorn.Config(
            admin_app,
            host=ADMIN_HOST,
            port=ADMIN_PORT,
            log_level="info" if ADMIN_DEBUG else "warning",
            access_log=ADMIN_DEBUG,
            reload=False,  # Отключаем reload в production
            workers=1
        )
        
        server = uvicorn.Server(config)
        
        # Запускаем в отдельном потоке
        def run_server():
            asyncio.run(server.serve())
        
        admin_thread = Thread(target=run_server, daemon=True)
        admin_thread.start()
        logger.info("✅ Админ-панель запущена")
        
        return admin_thread
    
    async def cleanup(self):
        """Корректное завершение работы"""
        logger.info("🛑 Завершение работы приложения...")
        
        self.running = False
        
        if self.bot:
            await self.bot.session.close()
            logger.info("✅ Бот остановлен")
        
        if self.db:
            # Закрываем соединения с базой данных
            logger.info("✅ База данных отключена")
        
        logger.info("✅ Приложение корректно завершено")
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов для корректного завершения"""
        def signal_handler(signum, frame):
            logger.info(f"📡 Получен сигнал {signum}, завершаем работу...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run(self):
        """Основной метод запуска приложения"""
        logger.info("=" * 50)
        logger.info("🚀 ЗАПУСК PRODUCTION ПРИЛОЖЕНИЯ")
        logger.info(f"📍 Окружение: {ENVIRONMENT}")
        logger.info(f"🗄️ База данных: {DATABASE_TYPE}")
        logger.info("=" * 50)
        
        try:
            # Настраиваем обработчики сигналов
            self.setup_signal_handlers()
            
            # Инициализируем базу данных
            await self.initialize_database()
            
            # Инициализируем бота
            await self.initialize_bot()
            
            # Запускаем админ-панель в отдельном потоке
            admin_thread = self.start_admin_panel()
            
            # Устанавливаем флаг работы
            self.running = True
            
            logger.info("🎉 Все сервисы запущены успешно!")
            logger.info("📊 Статистика:")
            
            # Получаем статистику
            stats = await self.db.get_bot_stats()
            logger.info(f"  👥 Пользователей: {stats['total_users']}")
            logger.info(f"  💎 Подписчиков: {stats['active_subscribers']}")
            logger.info(f"  📈 Запросов сегодня: {stats['requests_today']}")
            
            # Запускаем бота (основной цикл)
            await self.start_bot()
            
        except KeyboardInterrupt:
            logger.info("⌨️ Получен сигнал прерывания")
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            raise
        finally:
            await self.cleanup()

async def main():
    """Точка входа в приложение"""
    app = ProductionApp()
    await app.run()

if __name__ == "__main__":
    # Проверяем Python версию
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    
    # Проверяем обязательные переменные окружения
    required_vars = ['BOT_TOKEN', 'DATABASE_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        sys.exit(1)
    
    # Запускаем приложение
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Приложение остановлено пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        sys.exit(1)
