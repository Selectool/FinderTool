#!/usr/bin/env python3
"""
PostgreSQL Database Initialization Script
Инициализация PostgreSQL базы данных для production
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from database.production_db_manager import ProductionDatabaseManager
    from database.models import Database
    from utils.logging_config import setup_production_logging
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Убедитесь что скрипт запускается из корневой директории проекта")
    sys.exit(1)

# Настройка логирования
logger = setup_production_logging()

async def init_postgresql_database():
    """Инициализация PostgreSQL базы данных"""
    
    logger.info("🚀 Инициализация PostgreSQL базы данных...")
    
    # Проверяем переменные окружения
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL не установлен")
        return False
    
    if not database_url.startswith('postgresql://'):
        logger.error("❌ DATABASE_URL должен начинаться с postgresql://")
        return False
    
    logger.info(f"🔗 Подключение к: {database_url.split('@')[1] if '@' in database_url else 'скрыто'}")
    
    try:
        # Создаем менеджер базы данных
        db_manager = ProductionDatabaseManager(database_url)
        
        # Проверяем подключение
        logger.info("🔍 Проверка подключения к PostgreSQL...")
        if not await db_manager.verify_connection():
            logger.error("❌ Не удалось подключиться к PostgreSQL")
            return False
        
        logger.info("✅ Подключение к PostgreSQL установлено")
        
        # Выполняем миграции
        logger.info("🔄 Выполнение миграций...")
        await db_manager.run_safe_migrations()
        logger.info("✅ Миграции выполнены успешно")
        
        # Инициализируем Database объект для проверки таблиц
        logger.info("🏗️ Проверка дополнительных таблиц...")
        db = Database()
        await db.init_db()
        logger.info("✅ Дополнительные таблицы проверены")
        
        # Оптимизируем для production
        logger.info("⚡ Оптимизация для production...")
        await db_manager.optimize_for_production()
        logger.info("✅ Оптимизация завершена")
        
        # Получаем статистику
        logger.info("📊 Получение статистики базы данных...")
        stats = await db_manager.get_database_stats()
        
        logger.info("=" * 50)
        logger.info("📈 СТАТИСТИКА БАЗЫ ДАННЫХ:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        logger.info("=" * 50)
        
        logger.info("🎉 PostgreSQL база данных успешно инициализирована!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        logger.exception("Детали ошибки:")
        return False

async def create_admin_user():
    """Создание администратора"""
    
    admin_user_id = os.getenv('ADMIN_USER_ID')
    if not admin_user_id:
        logger.warning("⚠️ ADMIN_USER_ID не установлен, пропускаем создание админа")
        return
    
    try:
        admin_user_id = int(admin_user_id)
        logger.info(f"👤 Создание администратора: {admin_user_id}")
        
        db = Database()
        
        # Проверяем существование пользователя
        user = await db.get_user(admin_user_id)
        
        if not user:
            # Создаем пользователя
            await db.add_user(
                user_id=admin_user_id,
                username="admin",
                first_name="Admin",
                last_name="User"
            )
            logger.info("✅ Администратор создан")
        else:
            logger.info("ℹ️ Администратор уже существует")
        
        # Даем премиум статус
        await db.update_user_premium_status(admin_user_id, True)
        logger.info("✅ Премиум статус администратора обновлен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания администратора: {e}")

async def verify_database_health():
    """Проверка здоровья базы данных"""
    
    logger.info("🏥 Проверка здоровья базы данных...")
    
    try:
        db = Database()
        
        # Проверяем основные таблицы
        tables_to_check = [
            'users', 'subscriptions', 'requests', 
            'payments', 'broadcasts'
        ]
        
        for table in tables_to_check:
            try:
                # Простой запрос для проверки таблицы
                if table == 'users':
                    count = await db.get_users_count()
                elif table == 'subscriptions':
                    count = await db.get_active_subscribers_count()
                elif table == 'requests':
                    count = len(await db.get_user_requests(1, limit=1))
                else:
                    count = 0  # Для других таблиц
                
                logger.info(f"✅ Таблица {table}: OK (записей: {count})")
                
            except Exception as e:
                logger.warning(f"⚠️ Проблема с таблицей {table}: {e}")
        
        logger.info("✅ Проверка здоровья завершена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки здоровья: {e}")

async def main():
    """Основная функция"""
    
    logger.info("🚀 Запуск инициализации PostgreSQL...")
    
    # Проверяем окружение
    environment = os.getenv('ENVIRONMENT', 'development')
    logger.info(f"🌍 Окружение: {environment}")
    
    if environment == 'production':
        logger.warning("⚠️ ВНИМАНИЕ: PRODUCTION режим - реальные данные!")
    
    success = True
    
    # Инициализируем базу данных
    if not await init_postgresql_database():
        success = False
    
    # Создаем администратора
    if success:
        await create_admin_user()
    
    # Проверяем здоровье
    if success:
        await verify_database_health()
    
    if success:
        logger.info("🎉 Инициализация PostgreSQL завершена успешно!")
        logger.info("🚀 Теперь можно запускать приложение: python app.py")
    else:
        logger.error("❌ Инициализация завершилась с ошибками")
        sys.exit(1)

if __name__ == "__main__":
    # Проверяем Python версию
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    
    # Запускаем инициализацию
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Инициализация прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
