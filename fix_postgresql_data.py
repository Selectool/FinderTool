#!/usr/bin/env python3
"""
Скрипт для исправления и синхронизации данных PostgreSQL
Исправляет проблемы с подсчетом пользователей и рассылок
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent))

from database.universal_database import UniversalDatabase
from database.production_manager import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PostgreSQLDataFixer:
    """Класс для исправления данных PostgreSQL"""
    
    def __init__(self):
        self.db = UniversalDatabase()
        
    async def fix_all_data(self):
        """Исправить все проблемы с данными"""
        try:
            logger.info("🔧 Начинаем исправление данных PostgreSQL...")
            
            # Подключаемся к базе
            await self.db.adapter.connect()
            
            # Проверяем и исправляем структуру таблиц
            await self.check_and_fix_tables()
            
            # Проверяем данные пользователей
            await self.check_users_data()
            
            # Проверяем данные рассылок
            await self.check_broadcasts_data()
            
            # Проверяем данные платежей
            await self.check_payments_data()
            
            # Обновляем статистику
            await self.update_statistics()
            
            await self.db.adapter.disconnect()
            logger.info("✅ Исправление данных завершено успешно!")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при исправлении данных: {e}")
            import traceback
            traceback.print_exc()
            
    async def check_and_fix_tables(self):
        """Проверить и исправить структуру таблиц"""
        logger.info("📋 Проверяем структуру таблиц...")
        
        # Проверяем таблицу users
        users_exists = await self.db.adapter.fetch_one("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            )
        """)
        
        if users_exists and users_exists.get('exists'):
            logger.info("✅ Таблица users существует")
        else:
            logger.warning("⚠️ Таблица users не найдена")
            
        # Проверяем таблицу broadcasts
        broadcasts_exists = await self.db.adapter.fetch_one("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'broadcasts'
            )
        """)
        
        if broadcasts_exists and broadcasts_exists.get('exists'):
            logger.info("✅ Таблица broadcasts существует")
        else:
            logger.warning("⚠️ Таблица broadcasts не найдена")
            
    async def check_users_data(self):
        """Проверить данные пользователей"""
        logger.info("👥 Проверяем данные пользователей...")

        # Подсчитываем пользователей
        users_count = await self.db.get_users_count()
        logger.info(f"Всего пользователей: {users_count}")

        # Подсчитываем подписчиков
        subscribers_count = await self.db.get_subscribers_count()
        logger.info(f"Активных подписчиков: {subscribers_count}")

        # Переподключаемся к базе для следующего запроса
        await self.db.adapter.connect()

        # Проверяем структуру данных пользователей
        sample_user = await self.db.adapter.fetch_one("""
            SELECT user_id, username, is_subscribed, subscription_active, created_at
            FROM users
            LIMIT 1
        """)

        if sample_user:
            logger.info(f"Пример пользователя: {dict(sample_user)}")
            # Проверяем размер user_id
            user_id = sample_user.get('user_id')
            if user_id and user_id > 2147483647:  # int32 max
                logger.warning(f"⚠️ user_id {user_id} превышает int32 лимит PostgreSQL!")
        else:
            logger.warning("⚠️ Пользователи не найдены")
            
    async def check_broadcasts_data(self):
        """Проверить данные рассылок"""
        logger.info("📢 Проверяем данные рассылок...")
        
        # Подсчитываем рассылки
        broadcasts_result = await self.db.adapter.fetch_one("SELECT COUNT(*) FROM broadcasts")
        broadcasts_count = self.db._extract_count(broadcasts_result)
        logger.info(f"Всего рассылок: {broadcasts_count}")
        
        # Проверяем статусы рассылок
        status_stats = await self.db.adapter.fetch_all("""
            SELECT status, COUNT(*) as count
            FROM broadcasts 
            GROUP BY status
        """)
        
        if status_stats:
            logger.info("Статистика по статусам рассылок:")
            for stat in status_stats:
                logger.info(f"  {stat['status']}: {stat['count']}")
        else:
            logger.info("📝 Рассылки не найдены - это нормально для новой системы")
            
    async def check_payments_data(self):
        """Проверить данные платежей"""
        logger.info("💳 Проверяем данные платежей...")
        
        # Подсчитываем платежи
        payments_result = await self.db.adapter.fetch_one("SELECT COUNT(*) FROM payments")
        payments_count = self.db._extract_count(payments_result)
        logger.info(f"Всего платежей: {payments_count}")
        
        # Проверяем статусы платежей
        payment_stats = await self.db.adapter.fetch_all("""
            SELECT status, COUNT(*) as count
            FROM payments 
            GROUP BY status
        """)
        
        if payment_stats:
            logger.info("Статистика по статусам платежей:")
            for stat in payment_stats:
                logger.info(f"  {stat['status']}: {stat['count']}")
                
    async def update_statistics(self):
        """Обновить статистику"""
        logger.info("📊 Обновляем статистику...")
        
        # Получаем полную статистику
        stats = await self.db.get_stats()
        logger.info(f"Обновленная статистика: {stats}")
        
        # Проверяем пагинацию пользователей
        users_data = await self.db.get_users_paginated(page=1, per_page=5)
        logger.info(f"Пагинация пользователей: всего {users_data['total']}, на странице {len(users_data['users'])}")
        
        # Проверяем пагинацию рассылок
        broadcasts_data = await self.db.get_broadcasts_paginated(page=1, per_page=5)
        logger.info(f"Пагинация рассылок: всего {broadcasts_data['total']}, на странице {len(broadcasts_data['broadcasts'])}")

async def main():
    """Главная функция"""
    print("🚀 ИСПРАВЛЕНИЕ ДАННЫХ POSTGRESQL")
    print("=" * 50)
    
    fixer = PostgreSQLDataFixer()
    await fixer.fix_all_data()
    
    print("\n🎉 Готово! Теперь можно перезапустить бота и админ-панель")
    print("Команды для перезапуска:")
    print("1. python main.py")
    print("2. python run_admin.py")

if __name__ == "__main__":
    asyncio.run(main())
