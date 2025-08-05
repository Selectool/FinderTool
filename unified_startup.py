#!/usr/bin/env python3
"""
Unified Startup Script для Telegram Channel Finder Bot
Запускает и Telegram бота, и админ-панель в одном процессе
Оптимизирован для Railpack deployment
"""

import asyncio
import logging
import os
import sys
import signal
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/unified_startup.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)


class UnifiedService:
    """Unified сервис для запуска бота и админ-панели"""
    
    def __init__(self):
        self.bot_task = None
        self.admin_task = None
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Создаем директории
        Path("logs").mkdir(exist_ok=True)
        
        # Настройка обработчиков сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"🛑 Получен сигнал {signum}, начинаем graceful shutdown...")
        self.running = False
    
    async def init_database(self):
        """Инициализация базы данных"""
        try:
            logger.info("🔄 Инициализация базы данных...")
            from database.production_manager import init_production_database, db_manager
            from database.db_adapter import set_database
            
            await init_production_database()
            set_database(db_manager)
            logger.info("✅ База данных инициализирована")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            return False
    
    async def start_telegram_bot(self):
        """Запуск Telegram бота"""
        try:
            logger.info("🤖 Запуск Telegram бота...")
            
            from aiogram import Bot, Dispatcher
            from aiogram.client.default import DefaultBotProperties
            from aiogram.enums import ParseMode
            from aiogram.fsm.storage.memory import MemoryStorage
            
            from config import BOT_TOKEN
            from bot.middlewares.database import DatabaseMiddleware
            from bot.middlewares.role_middleware import RoleMiddleware
            from bot.handlers import basic, channels, subscription, admin, reply_menu
            
            # Создаем бота
            bot = Bot(
                token=BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            
            # Создаем диспетчер
            dp = Dispatcher(storage=MemoryStorage())
            
            # Регистрируем middleware
            dp.message.middleware(DatabaseMiddleware())
            dp.callback_query.middleware(DatabaseMiddleware())
            dp.message.middleware(RoleMiddleware())
            dp.callback_query.middleware(RoleMiddleware())
            
            # Регистрируем обработчики
            basic.register_handlers(dp)
            channels.register_handlers(dp)
            subscription.register_handlers(dp)
            admin.register_handlers(dp)
            reply_menu.register_handlers(dp)
            
            logger.info("✅ Telegram бот настроен и запущен")
            
            # Запускаем polling
            await dp.start_polling(bot)
            
        except Exception as e:
            logger.error(f"❌ Ошибка Telegram бота: {e}")
            raise
    
    def start_admin_panel(self):
        """Запуск админ-панели в отдельном потоке"""
        try:
            logger.info("🌐 Запуск админ-панели...")
            
            # Импортируем и запускаем админ-панель
            import subprocess
            import sys
            
            # Запускаем админ-панель как subprocess
            process = subprocess.Popen(
                [sys.executable, "run_admin.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            logger.info("✅ Админ-панель запущена")
            
            # Мониторим процесс
            while self.running:
                if process.poll() is not None:
                    logger.error("❌ Админ-панель остановилась")
                    break
                time.sleep(5)
            
            # Останавливаем процесс при завершении
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            
        except Exception as e:
            logger.error(f"❌ Ошибка админ-панели: {e}")
            raise
    
    async def health_check(self):
        """Проверка здоровья сервисов"""
        while self.running:
            try:
                # Проверяем БД
                from database.production_manager import db_manager
                db_health = await db_manager.health_check()
                
                # Проверяем админ-панель
                try:
                    import requests
                    admin_response = requests.get('http://localhost:8080/api/health', timeout=5)
                    admin_healthy = admin_response.status_code == 200
                except:
                    admin_healthy = False
                
                if db_health.get('status') == 'healthy' and admin_healthy:
                    logger.debug("💚 Все сервисы здоровы")
                else:
                    logger.warning(f"⚠️ Проблемы со здоровьем: БД={db_health.get('status')}, Админ={admin_healthy}")
                
                await asyncio.sleep(60)  # Проверяем каждую минуту
                
            except Exception as e:
                logger.error(f"❌ Ошибка health check: {e}")
                await asyncio.sleep(60)
    
    async def run(self):
        """Главный метод запуска unified сервиса"""
        logger.info("🚀 Запуск Unified Telegram Channel Finder Bot Service")
        logger.info(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'unknown')}")
        logger.info(f"📍 Database: {os.getenv('DATABASE_URL', 'unknown')[:50]}...")
        
        self.running = True
        
        # 1. Инициализация базы данных
        if not await self.init_database():
            logger.error("💥 Не удалось инициализировать базу данных")
            sys.exit(1)
        
        # 2. Запуск админ-панели в отдельном потоке
        admin_thread = threading.Thread(target=self.start_admin_panel, daemon=True)
        admin_thread.start()
        
        # Ждем запуска админ-панели
        await asyncio.sleep(5)
        
        # 3. Создаем задачи
        tasks = []
        
        # Telegram бот
        self.bot_task = asyncio.create_task(self.start_telegram_bot())
        tasks.append(self.bot_task)
        
        # Health check
        health_task = asyncio.create_task(self.health_check())
        tasks.append(health_task)
        
        logger.info("🎉 Все сервисы запущены!")
        logger.info("📱 Telegram бот: Активен")
        logger.info("🌐 Админ-панель: http://localhost:8080")
        
        try:
            # Ждем завершения задач
            await asyncio.gather(*tasks, return_exceptions=True)
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки")
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
        finally:
            logger.info("🔄 Завершение работы unified сервиса...")
            self.running = False
            
            # Отменяем задачи
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # Ждем завершения
            await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.info("✅ Unified сервис остановлен")


async def main():
    """Главная функция"""
    service = UnifiedService()
    await service.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Прерывание пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)
