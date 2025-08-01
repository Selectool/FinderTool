"""
Главный файл Telegram Channel Finder Bot
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, API_ID, API_HASH, IS_PRODUCTION
from database.models import Database
from database.production_manager import init_production_database
from bot.middlewares.database import DatabaseMiddleware
from bot.middlewares.role_middleware import RoleMiddleware
from bot.handlers import basic, channels, subscription, admin, reply_menu

# Настройка production логирования
from bot.utils.production_logger import setup_production_logging
setup_production_logging()

logger = logging.getLogger(__name__)

# Production-ready imports (с fallback для совместимости)
try:
    from bot.middlewares.production_security import (
        RateLimitMiddleware, SecurityMiddleware,
        TimeoutMiddleware, ProductionMonitoringMiddleware
    )
    from bot.utils.health_check import health_manager
    PRODUCTION_MODULES_AVAILABLE = True
    logger.info("✅ Production модули загружены")
except ImportError as e:
    logger.warning(f"⚠️ Production модули недоступны: {e}")
    logger.info("🔄 Запуск в базовом режиме без дополнительной защиты")
    PRODUCTION_MODULES_AVAILABLE = False

    # Создаем простые заглушки для production функций
    if IS_PRODUCTION:
        logger.info("🛡️ Создаем базовую production защиту...")

        # Простая проверка здоровья БД
        class SimpleHealthManager:
            async def perform_health_check(self):
                try:
                    # Проверяем только БД через production manager
                    from database.production_manager import db_manager
                    db_health = await db_manager.health_check()
                    return {
                        'status': 'healthy' if db_health['status'] == 'healthy' else 'degraded',
                        'components': {'database': db_health}
                    }
                except Exception as e:
                    return {'status': 'unhealthy', 'error': str(e)}

        health_manager = SimpleHealthManager()


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
    
    # Production-ready middleware stack
    if IS_PRODUCTION and PRODUCTION_MODULES_AVAILABLE:
        logger.info("🔒 Подключение production security middleware...")

        # Security middleware (первый уровень защиты)
        dp.message.middleware(SecurityMiddleware())
        dp.callback_query.middleware(SecurityMiddleware())

        # Rate limiting middleware
        dp.message.middleware(RateLimitMiddleware())
        dp.callback_query.middleware(RateLimitMiddleware())

        # Timeout middleware
        dp.message.middleware(TimeoutMiddleware())
        dp.callback_query.middleware(TimeoutMiddleware())

        # Monitoring middleware
        monitoring_middleware = ProductionMonitoringMiddleware()
        dp.message.middleware(monitoring_middleware)
        dp.callback_query.middleware(monitoring_middleware)

        logger.info("✅ Production middleware подключены")
    elif IS_PRODUCTION:
        logger.warning("⚠️ Production режим, но security модули недоступны")

    # Основные middleware
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
        logger.info(f"🤖 Бот запущен: @{bot_info.username} (ID: {bot_info.id})")

        # Production health check при запуске
        if IS_PRODUCTION and PRODUCTION_MODULES_AVAILABLE:
            logger.info("🏥 Выполняем начальную проверку здоровья системы...")
            try:
                health_status = await health_manager.perform_health_check()

                if health_status['status'] == 'unhealthy':
                    logger.error("❌ Система не готова к работе! Проверьте компоненты:")
                    for component, status in health_status['components'].items():
                        if status.get('status') != 'healthy':
                            logger.error(f"  - {component}: {status.get('error', 'unknown error')}")
                    return
                else:
                    logger.info(f"✅ Система готова к работе: {health_status['status']}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка health check: {e}")
                logger.info("🔄 Продолжаем запуск без health check")
        elif IS_PRODUCTION:
            logger.info("🏥 Health check модули недоступны, пропускаем проверку")

        # Запуск polling
        logger.info("🚀 Запуск polling...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
        if IS_PRODUCTION:
            # В production логируем дополнительную информацию
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        logger.info("🔄 Закрытие соединений...")
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
