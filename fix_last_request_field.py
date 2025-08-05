#!/usr/bin/env python3
"""
Скрипт для исправления поля last_request в PostgreSQL
Обновляет last_activity -> last_request для совместимости с админ-панелью
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db_adapter import DatabaseAdapter
from config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_last_request_field():
    """Исправить поле last_request в PostgreSQL"""
    try:
        adapter = DatabaseAdapter(DATABASE_URL)
        await adapter.connect()
        
        logger.info("🔧 Начинаем исправление поля last_request...")
        
        # Проверяем, есть ли колонка last_activity
        check_column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'last_activity'
        """
        
        result = await adapter.fetch_one(check_column_query)
        
        # Сначала проверяем, есть ли колонка last_request
        check_last_request_query = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'last_request'
        """

        last_request_result = await adapter.fetch_one(check_last_request_query)

        if not last_request_result:
            logger.info("➕ Добавляем колонку last_request...")
            add_column_query = "ALTER TABLE users ADD COLUMN last_request TIMESTAMP"
            await adapter.execute(add_column_query)
            logger.info("✅ Колонка last_request добавлена")
        else:
            logger.info("✅ Колонка last_request уже существует")

        # Теперь копируем данные из last_activity если она есть
        if result:
            logger.info("📋 Найдена колонка last_activity, копируем данные в last_request...")

            # Копируем данные из last_activity в last_request
            update_query = """
                UPDATE users
                SET last_request = last_activity
                WHERE last_activity IS NOT NULL AND (last_request IS NULL OR last_request < last_activity)
            """

            await adapter.execute(update_query)
            logger.info("✅ Данные скопированы из last_activity в last_request")

        else:
            logger.info("ℹ️ Колонка last_activity не найдена")
        
        # Обновляем last_request для пользователей, у которых есть запросы
        logger.info("🔄 Обновляем last_request на основе таблицы requests...")
        
        update_from_requests_query = """
            UPDATE users 
            SET last_request = (
                SELECT MAX(created_at) 
                FROM requests 
                WHERE requests.user_id = users.user_id
            )
            WHERE EXISTS (
                SELECT 1 FROM requests WHERE requests.user_id = users.user_id
            )
        """
        
        await adapter.execute(update_from_requests_query)
        logger.info("✅ Поле last_request обновлено на основе таблицы requests")
        
        # Проверяем результат
        count_query = """
            SELECT 
                COUNT(*) as total_users,
                COUNT(last_request) as users_with_last_request
            FROM users
        """
        
        result = await adapter.fetch_one(count_query)
        if result:
            total = result[0] if isinstance(result, (list, tuple)) else result.get('total_users', 0)
            with_last_request = result[1] if isinstance(result, (list, tuple)) else result.get('users_with_last_request', 0)
            
            logger.info(f"📊 Статистика:")
            logger.info(f"   Всего пользователей: {total}")
            logger.info(f"   С last_request: {with_last_request}")
            logger.info(f"   Без last_request: {total - with_last_request}")
        
        await adapter.disconnect()
        logger.info("🎉 Исправление поля last_request завершено успешно!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при исправлении поля last_request: {e}")
        try:
            await adapter.disconnect()
        except:
            pass
        raise


async def main():
    """Главная функция"""
    logger.info("🚀 Запуск скрипта исправления поля last_request")
    logger.info(f"🔗 База данных: {DATABASE_URL[:50]}...")
    
    try:
        await fix_last_request_field()
        logger.info("✅ Скрипт выполнен успешно!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения скрипта: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
