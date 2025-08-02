#!/usr/bin/env python3
"""
Production Launcher для Telegram Channel Finder Bot
Единый скрипт запуска для Dokploy/Railpack
Запускает Telegram бота + FastAPI админ-панель в одном процессе
"""

import asyncio
import logging
import multiprocessing
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Настройка логирования для production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/production.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

class ProductionLauncher:
    """Production launcher для единого запуска всех сервисов"""

    def __init__(self):
        self.processes = {}
        self.running = True

        # Создаем директории
        os.makedirs('logs', exist_ok=True)

        # Проверяем переменные окружения
        self._check_environment()
    
    async def initialize(self):
        """Инициализация приложения"""
        logger.info("🚀 Инициализация Railpack Production App...")
        
        # Проверяем переменные окружения
        self.check_environment()
        
        # Сбрасываем базу данных к чистому состоянию если нужно
        if os.getenv('RESET_DATABASE', 'false').lower() == 'true':
            logger.info("🔄 Сброс базы данных к чистому состоянию...")
            await reset_database_clean()
        
        # Создаем основное приложение
        self.app = ProductionApp()
        
        logger.info("✅ Инициализация завершена")
    
    def check_environment(self):
        """Проверка переменных окружения"""
        required_vars = ['BOT_TOKEN']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
            sys.exit(1)
        
        # Логируем конфигурацию
        logger.info("🔧 Конфигурация:")
        logger.info(f"  - BOT_TOKEN: {'✅ Установлен' if os.getenv('BOT_TOKEN') else '❌ Отсутствует'}")
        logger.info(f"  - DATABASE_URL: {'✅ PostgreSQL' if os.getenv('DATABASE_URL') else '⚠️ SQLite'}")
        logger.info(f"  - YOOKASSA_SHOP_ID: {'✅ Установлен' if os.getenv('YOOKASSA_SHOP_ID') else '⚠️ Отсутствует'}")
        logger.info(f"  - ADMIN_HOST: {os.getenv('ADMIN_HOST', '0.0.0.0')}")
        logger.info(f"  - ADMIN_PORT: {os.getenv('ADMIN_PORT', '8000')}")
        logger.info(f"  - ENVIRONMENT: {os.getenv('ENVIRONMENT', 'development')}")
    
    async def start_cleanup_service(self):
        """Запуск сервиса очистки платежей"""
        try:
            from database.models import Database
            db = Database()
            
            # Запускаем сервис очистки в фоне
            self.cleanup_task = asyncio.create_task(start_payment_cleanup(db))
            logger.info("🧹 Сервис очистки платежей запущен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске сервиса очистки: {e}")
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        def signal_handler(signum, frame):
            logger.info(f"📡 Получен сигнал {signum}, завершаем работу...")
            self.running = False
            
            # Отменяем задачи
            if self.cleanup_task and not self.cleanup_task.done():
                self.cleanup_task.cancel()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run(self):
        """Основной метод запуска"""
        try:
            # Инициализируем приложение
            await self.initialize()
            
            # Настраиваем обработчики сигналов
            self.setup_signal_handlers()
            
            # Запускаем сервис очистки
            await self.start_cleanup_service()
            
            # Устанавливаем флаг работы
            self.running = True
            
            logger.info("🎉 Railpack Production App запущен!")
            logger.info("📊 Доступные сервисы:")
            logger.info(f"  - Telegram Bot: @{os.getenv('BOT_USERNAME', 'FinderTool_bot')}")
            logger.info(f"  - Admin Panel: http://{os.getenv('ADMIN_HOST', '0.0.0.0')}:{os.getenv('ADMIN_PORT', '8000')}")
            logger.info(f"  - Payment Cleanup: ✅ Активен")
            
            # Запускаем основное приложение
            await self.app.run()
            
        except KeyboardInterrupt:
            logger.info("⌨️ Получен сигнал прерывания")
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Корректное завершение работы"""
        logger.info("🛑 Завершение работы Railpack Production App...")
        
        self.running = False
        
        # Останавливаем сервис очистки
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Останавливаем основное приложение
        if self.app:
            await self.app.cleanup()
        
        logger.info("✅ Railpack Production App корректно завершен")

async def main():
    """Точка входа для Railpack"""
    # Проверяем Python версию
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    
    # Создаем и запускаем приложение
    app = RailpackProductionApp()
    await app.run()

def sync_main():
    """Синхронная точка входа для совместимости"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Приложение остановлено пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    sync_main()
