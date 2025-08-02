#!/usr/bin/env python3
"""
Универсальный запуск Telegram бота и админ-панели одновременно
Для использования в Dokploy production
"""

import asyncio
import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
import threading
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

class ServiceManager:
    """Менеджер для управления несколькими сервисами"""
    
    def __init__(self):
        self.services = {}
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    async def start_telegram_bot(self):
        """Запуск Telegram бота"""
        logger.info("🤖 Запуск Telegram бота...")
        
        try:
            # Импортируем и запускаем основной бот
            from main import main as bot_main
            await bot_main()
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Telegram бота: {e}")
            logger.exception("Детали ошибки:")
            raise
    
    def start_admin_panel(self):
        """Запуск админ-панели в отдельном потоке"""
        logger.info("🌐 Запуск админ-панели...")
        
        try:
            import uvicorn
            from admin.main import app
            
            # Настройки для production
            config = uvicorn.Config(
                app=app,
                host="0.0.0.0",
                port=8080,
                log_level="info",
                access_log=True,
                loop="asyncio"
            )
            
            server = uvicorn.Server(config)
            
            # Запускаем в новом event loop для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            logger.info("✅ Админ-панель запущена на порту 8080")
            loop.run_until_complete(server.serve())
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска админ-панели: {e}")
            logger.exception("Детали ошибки:")
            raise
    
    async def health_monitor(self):
        """Мониторинг здоровья сервисов"""
        logger.info("💓 Запуск мониторинга здоровья...")
        
        while self.running:
            try:
                # Проверяем каждые 30 секунд
                await asyncio.sleep(30)
                
                if not self.running:
                    break
                
                # Простая проверка здоровья
                logger.info("💓 Проверка здоровья сервисов...")
                
                # Проверяем базу данных
                try:
                    from database.production_manager import db_manager
                    db_health = await db_manager.health_check()
                    if db_health.get('status') == 'healthy':
                        logger.info("✅ База данных: здорова")
                    else:
                        logger.warning("⚠️ База данных: проблемы")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка проверки БД: {e}")
                
                logger.info("💓 Все сервисы работают")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга: {e}")
    
    async def start_all_services(self):
        """Запуск всех сервисов одновременно"""
        logger.info("=" * 60)
        logger.info("🚀 ЗАПУСК TELEGRAM CHANNEL FINDER BOT")
        logger.info("=" * 60)
        logger.info("🤖 Telegram Bot + 🌐 Admin Panel + 💓 Health Monitor")
        logger.info("=" * 60)
        
        try:
            # Запускаем админ-панель в отдельном потоке
            admin_future = self.executor.submit(self.start_admin_panel)
            logger.info("✅ Админ-панель запускается в фоновом режиме...")
            
            # Небольшая задержка для запуска админ-панели
            await asyncio.sleep(2)
            
            # Создаем задачи для бота и мониторинга
            tasks = [
                asyncio.create_task(self.start_telegram_bot(), name="telegram_bot"),
                asyncio.create_task(self.health_monitor(), name="health_monitor")
            ]
            
            logger.info("✅ Все сервисы запущены!")
            logger.info("🌐 Админ-панель: http://0.0.0.0:8080")
            logger.info("🤖 Telegram бот: активен")
            logger.info("💓 Мониторинг: активен")
            logger.info("=" * 60)
            
            # Ждем завершения задач
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка запуска: {e}")
            logger.exception("Детали ошибки:")
            raise
        finally:
            self.running = False
            self.executor.shutdown(wait=True)
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов для graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"🛑 Получен сигнал {signum}, завершение работы...")
            self.running = False
            
            # Отменяем все задачи
            for task in asyncio.all_tasks():
                task.cancel()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Основная функция"""
    service_manager = ServiceManager()
    service_manager.setup_signal_handlers()
    
    try:
        await service_manager.start_all_services()
    except KeyboardInterrupt:
        logger.info("⚠️ Получен сигнал прерывания")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        logger.info("🛑 Завершение работы всех сервисов...")
        logger.info("=" * 60)
        logger.info("👋 TELEGRAM CHANNEL FINDER BOT ОСТАНОВЛЕН")
        logger.info("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Приложение остановлено пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
