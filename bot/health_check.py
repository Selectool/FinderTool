"""
Health check для Telegram бота
"""
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import BOT_TOKEN
from database.production_manager import db_manager

logger = logging.getLogger(__name__)


async def check_bot_health() -> bool:
    """
    Проверка здоровья Telegram бота
    
    Returns:
        bool: True если бот здоров, False если есть проблемы
    """
    try:
        # 1. Проверка переменных окружения
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN не настроен")
            return False
        
        # 2. Проверка подключения к базе данных
        try:
            health = await db_manager.health_check()
            if health.get('status') != 'healthy':
                logger.error(f"❌ Проблемы с БД: {health}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
            return False
        
        # 3. Проверка Telegram API (простая проверка токена)
        try:
            from aiogram import Bot
            bot = Bot(token=BOT_TOKEN)
            
            # Получаем информацию о боте
            bot_info = await bot.get_me()
            await bot.session.close()
            
            if not bot_info:
                logger.error("❌ Не удалось получить информацию о боте")
                return False
                
            logger.info(f"✅ Бот здоров: @{bot_info.username}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка Telegram API: {e}")
            return False
        
        logger.info("✅ Все проверки пройдены")
        return True
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка health check: {e}")
        return False


async def main():
    """Запуск health check"""
    is_healthy = await check_bot_health()
    sys.exit(0 if is_healthy else 1)


if __name__ == "__main__":
    asyncio.run(main())
