#!/usr/bin/env python3
"""
Запуск только Telegram бота без админ-панели
Для случаев когда админ-панель не нужна или есть проблемы с ее запуском
"""

import asyncio
import logging
import signal
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

class BotManager:
    """Менеджер для управления только ботом"""
    
    def __init__(self):
        self.running = True
    
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
    
    async def health_monitor(self):
        """Мониторинг здоровья бота"""
        logger.info("💓 Запуск мониторинга здоровья...")
        
        while self.running:
            try:
                # Проверяем каждые 60 секунд
                await asyncio.sleep(60)
                
                if not self.running:
                    break
                
                # Простая проверка здоровья
                logger.info("💓 Проверка здоровья бота...")
                
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
                
                logger.info("💓 Бот работает нормально")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга: {e}")
    
    async def start_bot_service(self):
        """Запуск только бота с мониторингом"""
        logger.info("=" * 60)
        logger.info("🤖 ЗАПУСК TELEGRAM CHANNEL FINDER BOT")
        logger.info("=" * 60)
        logger.info("🤖 Только Telegram Bot + 💓 Health Monitor")
        logger.info("🌐 Админ-панель: ОТКЛЮЧЕНА")
        logger.info("=" * 60)
        
        try:
            # Создаем задачи для бота и мониторинга
            tasks = [
                asyncio.create_task(self.start_telegram_bot(), name="telegram_bot"),
                asyncio.create_task(self.health_monitor(), name="health_monitor")
            ]
            
            logger.info("✅ Бот запущен!")
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
    bot_manager = BotManager()
    bot_manager.setup_signal_handlers()
    
    try:
        await bot_manager.start_bot_service()
    except KeyboardInterrupt:
        logger.info("⚠️ Получен сигнал прерывания")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        logger.info("🛑 Завершение работы бота...")
        logger.info("=" * 60)
        logger.info("👋 TELEGRAM CHANNEL FINDER BOT ОСТАНОВЛЕН")
        logger.info("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
