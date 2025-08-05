#!/usr/bin/env python3
"""
Скрипт для добавления поля unlimited_access в PostgreSQL
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


async def add_unlimited_access_field():
    """Добавить поле unlimited_access в PostgreSQL"""
    try:
        adapter = DatabaseAdapter(DATABASE_URL)
        await adapter.connect()
        
        logger.info("🔧 Начинаем добавление поля unlimited_access...")
        
        # Проверяем, есть ли колонка unlimited_access
        check_column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'unlimited_access'
        """
        
        result = await adapter.fetch_one(check_column_query)
        
        if not result:
            logger.info("➕ Добавляем колонку unlimited_access...")
            try:
                add_column_query = "ALTER TABLE users ADD COLUMN unlimited_access BOOLEAN DEFAULT FALSE"
                await adapter.execute(add_column_query)
                logger.info("✅ Колонка unlimited_access добавлена")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    logger.info("✅ Колонка unlimited_access уже существует (из ошибки)")
                else:
                    raise e
        else:
            logger.info("✅ Колонка unlimited_access уже существует")
        
        # Проверяем результат
        count_query = """
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN unlimited_access = TRUE THEN 1 END) as unlimited_users
            FROM users
        """
        
        result = await adapter.fetch_one(count_query)
        if result:
            total = result[0] if isinstance(result, (list, tuple)) else result.get('total_users', 0)
            unlimited = result[1] if isinstance(result, (list, tuple)) else result.get('unlimited_users', 0)
            
            logger.info(f"📊 Статистика:")
            logger.info(f"   Всего пользователей: {total}")
            logger.info(f"   С безлимитным доступом: {unlimited}")
        
        await adapter.disconnect()
        logger.info("🎉 Добавление поля unlimited_access завершено успешно!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении поля unlimited_access: {e}")
        try:
            await adapter.disconnect()
        except:
            pass
        raise


async def main():
    """Главная функция"""
    logger.info("🚀 Запуск скрипта добавления поля unlimited_access")
    logger.info(f"🔗 База данных: {DATABASE_URL[:50]}...")
    
    try:
        await add_unlimited_access_field()
        logger.info("✅ Скрипт выполнен успешно!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения скрипта: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
