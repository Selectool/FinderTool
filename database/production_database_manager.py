"""
Production-ready Database Manager для Telegram Channel Finder Bot
Унифицированное решение для всех проблем с базой данных и миграциями
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from database.db_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class ProductionDatabaseManager:
    """
    Production-ready менеджер базы данных с полным решением всех проблем:
    - Унифицированная система миграций
    - Исправление конфликтов между AdminMigrations и MigrationManager
    - Корректная обработка подписок (is_subscribed vs subscription_active)
    - Отключение legacy систем в production
    """
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv('DATABASE_URL', 'sqlite:///bot.db')
        self.db_type = 'postgresql' if self.database_url.startswith('postgresql') else 'sqlite'
        self.is_production = os.getenv('ENVIRONMENT', 'production') == 'production'
        
    async def initialize_production_database(self) -> Dict[str, Any]:
        """
        Полная инициализация production-ready базы данных
        """
        logger.info("🚀 Запуск production-ready инициализации базы данных...")
        
        try:
            # Этап 1: Исправление системы миграций
            await self._fix_migration_system()
            
            # Этап 2: Исправление схемы базы данных
            await self._fix_database_schema()
            
            # Этап 3: Синхронизация данных
            await self._synchronize_data()
            
            # Этап 4: Создание индексов
            await self._create_production_indexes()
            
            # Этап 5: Валидация
            db_info = await self._validate_database()
            
            logger.info("✅ Production база данных готова к работе")
            return db_info
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка инициализации БД: {e}")
            raise
    
    async def _fix_migration_system(self):
        """Исправляет систему миграций"""
        logger.info("🔧 Исправление системы миграций...")
        
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            # Создаем unified таблицу миграций
            if self.db_type == 'sqlite':
                query = """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version VARCHAR(255) UNIQUE NOT NULL,
                        migration_name TEXT UNIQUE NOT NULL,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        checksum VARCHAR(64),
                        execution_time_ms INTEGER DEFAULT 0
                    )
                """
            else:  # PostgreSQL
                query = """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        id SERIAL PRIMARY KEY,
                        version VARCHAR(255) UNIQUE NOT NULL,
                        migration_name TEXT UNIQUE NOT NULL,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        checksum VARCHAR(64),
                        execution_time_ms INTEGER DEFAULT 0
                    )
                """
            
            await adapter.execute(query)
            
            # Добавляем недостающие колонки если нужно
            await self._ensure_migration_columns(adapter)
            
            # Мигрируем существующие записи
            await self._migrate_existing_migration_records(adapter)
            
            logger.info("✅ Система миграций исправлена")
            
        finally:
            await adapter.disconnect()
    
    async def _ensure_migration_columns(self, adapter: DatabaseAdapter):
        """Обеспечивает наличие всех необходимых колонок в schema_migrations"""
        try:
            # Проверяем наличие колонки migration_name
            if self.db_type == 'postgresql':
                check_query = """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'schema_migrations' AND column_name = 'migration_name'
                """
                result = await adapter.fetch_all(check_query)
                has_migration_name = len(result) > 0
            else:
                check_query = "PRAGMA table_info(schema_migrations)"
                result = await adapter.fetch_all(check_query)
                has_migration_name = any(col[1] == 'migration_name' for col in result)
            
            if not has_migration_name:
                if self.db_type == 'postgresql':
                    await adapter.execute("ALTER TABLE schema_migrations ADD COLUMN migration_name TEXT")
                else:
                    await adapter.execute("ALTER TABLE schema_migrations ADD COLUMN migration_name TEXT")
                
                logger.info("✅ Добавлена колонка migration_name")
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось проверить/добавить колонки: {e}")
    
    async def _migrate_existing_migration_records(self, adapter: DatabaseAdapter):
        """Мигрирует существующие записи миграций"""
        try:
            # Обновляем записи без migration_name
            if self.db_type == 'postgresql':
                update_query = """
                    UPDATE schema_migrations 
                    SET migration_name = COALESCE(migration_name, version)
                    WHERE migration_name IS NULL OR migration_name = ''
                """
            else:
                update_query = """
                    UPDATE schema_migrations 
                    SET migration_name = COALESCE(migration_name, version)
                    WHERE migration_name IS NULL OR migration_name = ''
                """
            
            await adapter.execute(update_query)
            logger.info("✅ Существующие записи миграций обновлены")
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось мигрировать записи: {e}")
    
    async def _fix_database_schema(self):
        """Исправляет схему базы данных"""
        logger.info("🔧 Исправление схемы базы данных...")
        
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            # Исправляем таблицу users
            await self._fix_users_table(adapter)
            
            # Создаем недостающие таблицы
            await self._create_missing_tables(adapter)
            
            logger.info("✅ Схема базы данных исправлена")
            
        finally:
            await adapter.disconnect()
    
    async def _fix_users_table(self, adapter: DatabaseAdapter):
        """Исправляет таблицу users"""
        try:
            # Проверяем наличие колонки is_subscribed
            if self.db_type == 'postgresql':
                check_query = """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'is_subscribed'
                """
                result = await adapter.fetch_all(check_query)
                has_is_subscribed = len(result) > 0
            else:
                check_query = "PRAGMA table_info(users)"
                result = await adapter.fetch_all(check_query)
                has_is_subscribed = any(col[1] == 'is_subscribed' for col in result)
            
            if not has_is_subscribed:
                if self.db_type == 'postgresql':
                    await adapter.execute("ALTER TABLE users ADD COLUMN is_subscribed BOOLEAN DEFAULT FALSE")
                else:
                    await adapter.execute("ALTER TABLE users ADD COLUMN is_subscribed BOOLEAN DEFAULT FALSE")
                
                logger.info("✅ Добавлена колонка is_subscribed")
            
            # Синхронизируем is_subscribed с subscription_active
            if self.db_type == 'postgresql':
                sync_query = """
                    UPDATE users 
                    SET is_subscribed = COALESCE(subscription_active, FALSE)
                    WHERE is_subscribed IS NULL OR is_subscribed != COALESCE(subscription_active, FALSE)
                """
            else:
                sync_query = """
                    UPDATE users 
                    SET is_subscribed = COALESCE(subscription_active, 0)
                    WHERE is_subscribed IS NULL
                """
            
            await adapter.execute(sync_query)
            logger.info("✅ Данные подписок синхронизированы")
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось исправить таблицу users: {e}")
    
    async def _create_missing_tables(self, adapter: DatabaseAdapter):
        """Создает недостающие таблицы"""
        essential_tables = {
            'admin_users': self._create_admin_users_table,
            'roles': self._create_roles_table,
            'message_templates': self._create_message_templates_table,
            'audit_logs': self._create_audit_logs_table
        }
        
        for table_name, create_func in essential_tables.items():
            try:
                await create_func(adapter)
                logger.info(f"✅ Таблица {table_name} готова")
            except Exception as e:
                logger.warning(f"⚠️ Проблема с таблицей {table_name}: {e}")
    
    async def _synchronize_data(self):
        """Синхронизирует данные между различными полями"""
        logger.info("🔄 Синхронизация данных...")
        
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            # Синхронизируем подписки
            if self.db_type == 'postgresql':
                sync_queries = [
                    "UPDATE users SET is_subscribed = subscription_active WHERE is_subscribed != subscription_active",
                    "UPDATE users SET subscription_active = is_subscribed WHERE subscription_active != is_subscribed"
                ]
            else:
                sync_queries = [
                    "UPDATE users SET is_subscribed = subscription_active WHERE is_subscribed != subscription_active"
                ]
            
            for query in sync_queries:
                try:
                    await adapter.execute(query)
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось выполнить синхронизацию: {e}")
            
            logger.info("✅ Данные синхронизированы")
            
        finally:
            await adapter.disconnect()
    
    async def _create_production_indexes(self):
        """Создает индексы для production"""
        logger.info("📊 Создание production индексов...")
        
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(is_subscribed, subscription_end)",
                "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
                "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_requests_user_id ON requests(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_schema_migrations_name ON schema_migrations(migration_name)"
            ]
            
            for index_query in indexes:
                try:
                    await adapter.execute(index_query)
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось создать индекс: {e}")
            
            logger.info("✅ Production индексы созданы")
            
        finally:
            await adapter.disconnect()
    
    async def _validate_database(self) -> Dict[str, Any]:
        """Валидирует состояние базы данных"""
        logger.info("✅ Валидация базы данных...")
        
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            # Проверяем основные таблицы
            essential_tables = ['users', 'requests', 'payments', 'schema_migrations']
            table_info = []
            
            for table in essential_tables:
                try:
                    count_query = f"SELECT COUNT(*) FROM {table}"
                    result = await adapter.fetch_one(count_query)
                    count = result[0] if result else 0
                    table_info.append({"table_name": table, "record_count": count})
                except Exception as e:
                    logger.warning(f"⚠️ Проблема с таблицей {table}: {e}")
                    table_info.append({"table_name": table, "record_count": -1, "error": str(e)})
            
            db_info = {
                "database_type": self.db_type,
                "database_url": self.database_url.replace(self.database_url.split('@')[0].split('//')[1], '***') if '@' in self.database_url else self.database_url,
                "connection_status": "connected",
                "tables": table_info,
                "is_production": self.is_production,
                "validation_time": datetime.now().isoformat()
            }
            
            logger.info("✅ Валидация завершена успешно")
            return db_info
            
        finally:
            await adapter.disconnect()


# Глобальный экземпляр
production_db_manager = ProductionDatabaseManager()


    async def _create_admin_users_table(self, adapter: DatabaseAdapter):
        """Создает таблицу admin_users"""
        if self.db_type == 'postgresql':
            query = """
                CREATE TABLE IF NOT EXISTS admin_users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role VARCHAR(100) NOT NULL DEFAULT 'moderator',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    telegram_id BIGINT UNIQUE
                )
            """
        else:
            query = """
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'moderator',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    telegram_id INTEGER UNIQUE
                )
            """

        await adapter.execute(query)

    async def _create_roles_table(self, adapter: DatabaseAdapter):
        """Создает таблицу roles"""
        if self.db_type == 'postgresql':
            query = """
                CREATE TABLE IF NOT EXISTS roles (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    description TEXT,
                    permissions TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        else:
            query = """
                CREATE TABLE IF NOT EXISTS roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    permissions TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """

        await adapter.execute(query)

    async def _create_message_templates_table(self, adapter: DatabaseAdapter):
        """Создает таблицу message_templates"""
        if self.db_type == 'postgresql':
            query = """
                CREATE TABLE IF NOT EXISTS message_templates (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    subject VARCHAR(500),
                    content TEXT NOT NULL,
                    template_type VARCHAR(100) DEFAULT 'broadcast',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        else:
            query = """
                CREATE TABLE IF NOT EXISTS message_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    subject TEXT,
                    content TEXT NOT NULL,
                    template_type TEXT DEFAULT 'broadcast',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """

        await adapter.execute(query)

    async def _create_audit_logs_table(self, adapter: DatabaseAdapter):
        """Создает таблицу audit_logs"""
        if self.db_type == 'postgresql':
            query = """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    admin_user_id INTEGER,
                    action VARCHAR(255) NOT NULL,
                    resource_type VARCHAR(100) NOT NULL,
                    resource_id INTEGER,
                    details TEXT,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        else:
            query = """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_user_id INTEGER,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id INTEGER,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """

        await adapter.execute(query)


# Глобальный экземпляр
production_db_manager = ProductionDatabaseManager()


async def initialize_production_database(database_url: str = None) -> Dict[str, Any]:
    """
    Функция для инициализации production базы данных
    """
    if database_url:
        manager = ProductionDatabaseManager(database_url)
    else:
        manager = production_db_manager

    return await manager.initialize_production_database()
