"""
Главный файл для запуска только Telegram бота
Отдельный сервис для Dokploy
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, API_ID, API_HASH, IS_PRODUCTION
from database.production_manager import init_production_database, db_manager
from database.db_adapter import set_database
from bot.middlewares.database import DatabaseMiddleware
from bot.middlewares.role_middleware import RoleMiddleware
# Импорты обработчиков будут в функции setup_bot

# Настройка production логирования
from bot.utils.production_logger import setup_production_logging
setup_production_logging()

logger = logging.getLogger(__name__)


async def init_bot_database():
    """Инициализация базы данных для бота"""
    try:
        logger.info("🔄 Инициализация базы данных...")
        await init_production_database()
        set_database(db_manager)
        logger.info("✅ База данных инициализирована")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return False


async def setup_bot():
    """Настройка бота"""
    logger.info("🤖 Настройка Telegram бота...")
    
    # Создаем бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создаем диспетчер
    dp = Dispatcher(storage=MemoryStorage())
    
    # Получаем экземпляр базы данных
    from database.universal_database import UniversalDatabase
    from config import DATABASE_URL
    db = UniversalDatabase(DATABASE_URL)

    # Регистрируем middleware
    dp.message.middleware(DatabaseMiddleware(db))
    dp.callback_query.middleware(DatabaseMiddleware(db))
    dp.message.middleware(RoleMiddleware())
    dp.callback_query.middleware(RoleMiddleware())
    
    # Регистрируем обработчики через роутеры
    try:
        # Используем централизованную регистрацию
        from bot.handlers.register import register_handlers
        register_handlers(dp)
    except ImportError:
        # Fallback - регистрируем роутеры напрямую
        logger.warning("⚠️ Используем fallback регистрацию роутеров")
        from bot.handlers import basic, channels, subscription, admin, reply_menu

        dp.include_router(admin.router)  # Админ роутер первым для FSM
        dp.include_router(reply_menu.router)  # Reply клавиатура
        dp.include_router(basic.router)
        dp.include_router(channels.router)
        dp.include_router(subscription.router)
    
    logger.info("✅ Telegram бот настроен")
    return bot, dp


async def main():
    """Главная функция запуска бота"""
    logger.info("🚀 Запуск Telegram Channel Finder Bot")
    logger.info(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'unknown')}")
    logger.info(f"🔧 Service Type: {os.getenv('SERVICE_TYPE', 'unknown')}")
    
    # Инициализация базы данных
    if not await init_bot_database():
        logger.error("💥 Не удалось инициализировать базу данных")
        sys.exit(1)
    
    # Настройка бота
    try:
        bot, dp = await setup_bot()
    except Exception as e:
        logger.error(f"💥 Ошибка настройки бота: {e}")
        sys.exit(1)
    
    # Запуск бота
    try:
        logger.info("🎉 Telegram бот запущен и готов к работе!")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        raise
    finally:
        logger.info("🔄 Завершение работы бота...")
        await bot.session.close()
        if hasattr(db_manager, 'close'):
            await db_manager.close()
        logger.info("✅ Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Прерывание пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)
