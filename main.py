"""
Главный файл Telegram Channel Finder Bot
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, API_ID, API_HASH
from database.models import Database
from database.production_manager import init_production_database
from bot.middlewares.database import DatabaseMiddleware
from bot.middlewares.role_middleware import RoleMiddleware
from bot.handlers import basic, channels, subscription, admin, reply_menu

# Настройка production логирования
from bot.utils.production_logger import setup_production_logging
setup_production_logging()

logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота"""
    
    # Проверяем наличие необходимых конфигураций
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен!")
        return
    
    if not API_ID or not API_HASH:
        logger.error("API_ID или API_HASH не установлены!")
        logger.error("Получите их на https://my.telegram.org")
        return
    
    # Инициализация бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Инициализация диспетчера с хранилищем состояний
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Production-ready инициализация базы данных
    logger.info("Инициализация production-ready базы данных...")
    db_info = await init_production_database()

    if db_info is None:
        logger.error("Критическая ошибка инициализации базы данных!")
        return

    logger.info(f"База данных инициализирована: {db_info.get('database_type', 'unknown')}")

    # Инициализация legacy Database для совместимости
    db = Database()
    await db.init_db()
    logger.info("Legacy Database инициализирована для совместимости")
    
    # Подключение middleware
    dp.message.middleware(DatabaseMiddleware(db))
    dp.callback_query.middleware(DatabaseMiddleware(db))
    dp.pre_checkout_query.middleware(DatabaseMiddleware(db))

    # Подключение middleware для ролей (после DatabaseMiddleware)
    dp.message.middleware(RoleMiddleware())
    dp.callback_query.middleware(RoleMiddleware())
    
    # Подключение роутеров
    dp.include_router(admin.router)  # Админ роутер должен быть первым для FSM состояний
    dp.include_router(reply_menu.router)  # Reply клавиатура
    dp.include_router(basic.router)
    dp.include_router(channels.router)
    dp.include_router(subscription.router)

    # Подключение роутера разработчика
    from bot.handlers import developer
    dp.include_router(developer.router)

    # Подключение роутера управления ролями
    from bot.handlers import role_management
    dp.include_router(role_management.router)
    
    logger.info("Роутеры подключены")
    
    try:
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"Бот запущен: @{bot_info.username}")
        
        # Запуск polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
