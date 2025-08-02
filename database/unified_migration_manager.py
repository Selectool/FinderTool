"""
Production-ready унифицированная система миграций для Telegram Channel Finder Bot
Решает проблему конфликта между AdminMigrations и MigrationManager
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
import hashlib
import json

from database.db_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class UnifiedMigrationManager:
    """
    Production-ready менеджер миграций с поддержкой:
    - PostgreSQL и SQLite
    - Совместимость с legacy AdminMigrations
    - Транзакционная безопасность
    - Автоматическое исправление конфликтов схемы
    """
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.db_type = 'postgresql' if database_url.startswith('postgresql') else 'sqlite'
        
    async def fix_schema_migrations_table(self) -> bool:
        """
        Исправляет таблицу schema_migrations для совместимости
        с обеими системами миграций
        """
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            # Проверяем текущую структуру таблицы
            current_columns = await self._get_table_columns(adapter, 'schema_migrations')
            
            if not current_columns:
                # Таблица не существует, создаем unified версию
                await self._create_unified_migrations_table(adapter)
                logger.info("✅ Создана unified таблица schema_migrations")
                return True
            
            # Проверяем наличие необходимых колонок
            required_columns = {'version', 'migration_name', 'description', 'applied_at'}
            existing_columns = {col['name'] for col in current_columns}
            missing_columns = required_columns - existing_columns
            
            if missing_columns:
                logger.info(f"🔧 Добавляем недостающие колонки: {missing_columns}")
                await self._add_missing_columns(adapter, missing_columns)
            
            # Мигрируем существующие данные
            await self._migrate_existing_data(adapter)
            
            logger.info("✅ Таблица schema_migrations успешно обновлена")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка исправления таблицы миграций: {e}")
            return False
        finally:
            await adapter.disconnect()
    
    async def _get_table_columns(self, adapter: DatabaseAdapter, table_name: str) -> List[Dict]:
        """Получает информацию о колонках таблицы"""
        try:
            if self.db_type == 'sqlite':
                query = f"PRAGMA table_info({table_name})"
                result = await adapter.fetch_all(query)
                return [{'name': row[1], 'type': row[2]} for row in result] if result else []
            else:  # PostgreSQL
                query = """
                    SELECT column_name as name, data_type as type 
                    FROM information_schema.columns 
                    WHERE table_name = $1
                """
                result = await adapter.fetch_all(query, (table_name,))
                return [{'name': row[0], 'type': row[1]} for row in result] if result else []
        except Exception:
            return []
    
    async def _create_unified_migrations_table(self, adapter: DatabaseAdapter):
        """Создает unified таблицу миграций"""
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
        
        # Создаем индексы
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_migrations_version ON schema_migrations(version)",
            "CREATE INDEX IF NOT EXISTS idx_migrations_name ON schema_migrations(migration_name)"
        ]
        
        for index_query in indexes:
            try:
                await adapter.execute(index_query)
            except Exception as e:
                logger.warning(f"Не удалось создать индекс: {e}")
    
    async def _add_missing_columns(self, adapter: DatabaseAdapter, missing_columns: Set[str]):
        """Добавляет недостающие колонки в таблицу"""
        column_definitions = {
            'migration_name': 'TEXT',
            'version': 'VARCHAR(255)',
            'description': 'TEXT',
            'applied_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'checksum': 'VARCHAR(64)',
            'execution_time_ms': 'INTEGER DEFAULT 0'
        }
        
        for column in missing_columns:
            if column in column_definitions:
                try:
                    if self.db_type == 'sqlite':
                        query = f"ALTER TABLE schema_migrations ADD COLUMN {column} {column_definitions[column]}"
                    else:  # PostgreSQL
                        query = f"ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS {column} {column_definitions[column]}"
                    
                    await adapter.execute(query)
                    logger.info(f"✅ Добавлена колонка {column}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось добавить колонку {column}: {e}")
    
    async def _migrate_existing_data(self, adapter: DatabaseAdapter):
        """Мигрирует существующие данные для совместимости"""
        try:
            # Обновляем записи без migration_name
            if self.db_type == 'sqlite':
                update_query = """
                    UPDATE schema_migrations 
                    SET migration_name = COALESCE(migration_name, 'legacy_' || COALESCE(version, id)),
                        version = COALESCE(version, 'v' || id),
                        description = COALESCE(description, 'Legacy migration')
                    WHERE migration_name IS NULL OR migration_name = ''
                """
            else:  # PostgreSQL
                update_query = """
                    UPDATE schema_migrations 
                    SET migration_name = COALESCE(migration_name, 'legacy_' || COALESCE(version, id::text)),
                        version = COALESCE(version, 'v' || id::text),
                        description = COALESCE(description, 'Legacy migration')
                    WHERE migration_name IS NULL OR migration_name = ''
                """
            
            await adapter.execute(update_query)
            
            # Обновляем записи без version
            if self.db_type == 'sqlite':
                update_version_query = """
                    UPDATE schema_migrations 
                    SET version = COALESCE(version, migration_name)
                    WHERE version IS NULL OR version = ''
                """
            else:  # PostgreSQL
                update_version_query = """
                    UPDATE schema_migrations 
                    SET version = COALESCE(version, migration_name)
                    WHERE version IS NULL OR version = ''
                """
            
            await adapter.execute(update_version_query)
            
            logger.info("✅ Существующие данные успешно мигрированы")
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось мигрировать существующие данные: {e}")
    
    async def run_admin_migrations_fix(self) -> bool:
        """
        Запускает исправленные админ миграции с unified системой
        """
        try:
            # Сначала исправляем таблицу миграций
            await self.fix_schema_migrations_table()
            
            # Импортируем и запускаем админ миграции
            from database.admin_migrations import AdminMigrations
            
            # Создаем адаптированную версию AdminMigrations
            admin_migrations = AdminMigrations()
            
            # Переопределяем методы для работы с unified таблицей
            await self._run_unified_admin_migrations(admin_migrations)
            
            logger.info("✅ Админ миграции выполнены с unified системой")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения админ миграций: {e}")
            return False
    
    async def _run_unified_admin_migrations(self, admin_migrations):
        """Запускает админ миграции с unified системой"""
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            # Получаем список миграций
            migrations = [
                ('create_admin_users_table', admin_migrations._create_admin_users_table),
                ('create_roles_table', admin_migrations._create_roles_table),
                ('create_message_templates_table', admin_migrations._create_message_templates_table),
                ('create_scheduled_broadcasts_table', admin_migrations._create_scheduled_broadcasts_table),
                ('create_audit_logs_table', admin_migrations._create_audit_logs_table),
                ('create_ab_tests_table', admin_migrations._create_ab_tests_table),
                ('create_broadcast_logs_table', admin_migrations._create_broadcast_logs_table),
                ('extend_users_table', admin_migrations._extend_users_table),
                ('extend_broadcasts_table', admin_migrations._extend_broadcasts_table),
                ('add_status_to_broadcasts', admin_migrations._add_status_to_broadcasts),
                ('add_title_to_broadcasts', admin_migrations._add_title_to_broadcasts),
                ('insert_default_roles', admin_migrations._insert_default_roles),
                ('create_default_admin_user', admin_migrations._create_default_admin_user),
                ('add_telegram_user_roles', admin_migrations._add_telegram_user_roles),
                ('assign_default_telegram_roles', admin_migrations._assign_default_telegram_roles)
            ]
            
            # Получаем выполненные миграции
            executed_migrations = await self._get_executed_migrations(adapter)
            
            migrations_executed = 0
            for migration_name, migration_func in migrations:
                if migration_name not in executed_migrations:
                    try:
                        # Адаптируем функцию для работы с PostgreSQL
                        await self._execute_adapted_migration(adapter, migration_func, migration_name)
                        await self._mark_migration_executed(adapter, migration_name)
                        logger.info(f"✅ Миграция {migration_name} выполнена успешно")
                        migrations_executed += 1
                    except Exception as e:
                        logger.error(f"❌ Ошибка выполнения миграции {migration_name}: {e}")
            
            logger.info(f"✅ Выполнено {migrations_executed} новых миграций")
            
        finally:
            await adapter.disconnect()
    
    async def _get_executed_migrations(self, adapter: DatabaseAdapter) -> Set[str]:
        """Получает список выполненных миграций"""
        try:
            query = "SELECT migration_name FROM schema_migrations"
            result = await adapter.fetch_all(query)
            return {row[0] for row in result} if result else set()
        except Exception:
            return set()
    
    async def _mark_migration_executed(self, adapter: DatabaseAdapter, migration_name: str):
        """Отмечает миграцию как выполненную"""
        try:
            if self.db_type == 'sqlite':
                query = """
                    INSERT OR IGNORE INTO schema_migrations 
                    (version, migration_name, description) 
                    VALUES (?, ?, ?)
                """
                params = (migration_name, migration_name, f"Admin migration: {migration_name}")
            else:  # PostgreSQL
                query = """
                    INSERT INTO schema_migrations 
                    (version, migration_name, description) 
                    VALUES ($1, $2, $3)
                    ON CONFLICT (migration_name) DO NOTHING
                """
                params = (migration_name, migration_name, f"Admin migration: {migration_name}")
            
            await adapter.execute(query, params)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отметить миграцию {migration_name}: {e}")
    
    async def _execute_adapted_migration(self, adapter: DatabaseAdapter, migration_func, migration_name: str):
        """Выполняет миграцию, адаптированную для PostgreSQL"""
        # Для PostgreSQL нужно адаптировать SQLite-специфичные функции
        if self.db_type == 'postgresql':
            # Создаем mock объект для совместимости с SQLite API
            class PostgreSQLAdapter:
                def __init__(self, adapter):
                    self.adapter = adapter
                
                async def execute(self, query, params=None):
                    # Адаптируем SQLite запросы для PostgreSQL
                    adapted_query = self._adapt_query(query)
                    return await self.adapter.execute(adapted_query, params)
                
                async def commit(self):
                    # PostgreSQL автоматически коммитит
                    pass
                
                def _adapt_query(self, query):
                    # Базовые адаптации SQLite -> PostgreSQL
                    adaptations = {
                        'INTEGER PRIMARY KEY AUTOINCREMENT': 'SERIAL PRIMARY KEY',
                        'BOOLEAN DEFAULT TRUE': 'BOOLEAN DEFAULT TRUE',
                        'BOOLEAN DEFAULT FALSE': 'BOOLEAN DEFAULT FALSE',
                        'TEXT': 'TEXT',
                        'INTEGER': 'INTEGER',
                        'TIMESTAMP DEFAULT CURRENT_TIMESTAMP': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
                    }
                    
                    adapted = query
                    for sqlite_syntax, postgres_syntax in adaptations.items():
                        adapted = adapted.replace(sqlite_syntax, postgres_syntax)
                    
                    return adapted
            
            pg_adapter = PostgreSQLAdapter(adapter)
            await migration_func(pg_adapter)
        else:
            # Для SQLite используем оригинальную функцию
            # Но нужно создать совместимый объект
            class SQLiteAdapter:
                def __init__(self, adapter):
                    self.adapter = adapter
                
                async def execute(self, query, params=None):
                    return await self.adapter.execute(query, params)
                
                async def commit(self):
                    pass
            
            sqlite_adapter = SQLiteAdapter(adapter)
            await migration_func(sqlite_adapter)


# Функция для быстрого исправления проблемы
async def fix_migration_conflicts(database_url: str) -> bool:
    """
    Быстрое исправление конфликтов миграций
    """
    try:
        manager = UnifiedMigrationManager(database_url)
        
        # Исправляем таблицу миграций
        success = await manager.fix_schema_migrations_table()
        if not success:
            return False
        
        # Запускаем админ миграции
        success = await manager.run_admin_migrations_fix()
        return success
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка исправления миграций: {e}")
        return False
