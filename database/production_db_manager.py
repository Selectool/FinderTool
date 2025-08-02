"""
Production-Ready Database Manager для PostgreSQL
Безопасные миграции без потери данных для Railpack/Dokploy
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import asyncpg

logger = logging.getLogger(__name__)

class ProductionDatabaseManager:
    """Production-ready менеджер базы данных с безопасными миграциями"""
    
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.connection_pool: Optional[asyncpg.Pool] = None
    
    async def verify_connection(self) -> bool:
        """Проверка подключения к PostgreSQL"""
        try:
            logger.info("🔍 Проверка подключения к PostgreSQL...")
            
            # Создаем пул соединений
            self.connection_pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            
            # Тестируем подключение
            async with self.connection_pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            
            logger.info("✅ Подключение к PostgreSQL успешно")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к PostgreSQL: {e}")
            raise
    
    async def run_safe_migrations(self) -> bool:
        """
        Безопасное выполнение миграций без потери данных
        Проверяет существование данных перед выполнением миграций
        """
        try:
            logger.info("🔄 Выполнение безопасных миграций...")
            
            if not self.connection_pool:
                await self.verify_connection()
            
            async with self.connection_pool.acquire() as conn:
                # Проверяем существование основных таблиц
                existing_tables = await self._check_existing_tables(conn)
                
                if existing_tables:
                    logger.info(f"📋 Найдены существующие таблицы: {', '.join(existing_tables)}")
                    
                    # Проверяем наличие данных
                    has_data = await self._check_existing_data(conn, existing_tables)
                    
                    if has_data:
                        logger.info("📊 Обнаружены существующие данные - выполняем инкрементальные миграции")
                        await self._run_incremental_migrations(conn, existing_tables)
                    else:
                        logger.info("📊 Данные не найдены - выполняем полную инициализацию")
                        await self._run_full_initialization(conn)
                else:
                    logger.info("📋 Таблицы не найдены - выполняем полную инициализацию")
                    await self._run_full_initialization(conn)
                
                # Создаем индексы для производительности
                await self._create_performance_indexes(conn)
                
                # Обновляем системные настройки
                await self._update_system_settings(conn)
            
            logger.info("✅ Миграции выполнены успешно")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при выполнении миграций: {e}")
            raise
    
    async def _check_existing_tables(self, conn: asyncpg.Connection) -> List[str]:
        """Проверка существующих таблиц"""
        try:
            query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """
            
            rows = await conn.fetch(query)
            return [row['table_name'] for row in rows]
            
        except Exception as e:
            logger.warning(f"Не удалось проверить существующие таблицы: {e}")
            return []
    
    async def _check_existing_data(self, conn: asyncpg.Connection, tables: List[str]) -> bool:
        """Проверка наличия данных в существующих таблицах"""
        try:
            data_tables = ['users', 'payments', 'user_requests']
            
            for table in data_tables:
                if table in tables:
                    count = await conn.fetchval(f'SELECT COUNT(*) FROM {table}')
                    if count > 0:
                        logger.info(f"📊 Найдено {count} записей в таблице {table}")
                        return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Не удалось проверить данные: {e}")
            return False
    
    async def _run_full_initialization(self, conn: asyncpg.Connection):
        """Полная инициализация базы данных"""
        logger.info("🔄 Полная инициализация базы данных...")
        
        # SQL для создания всех таблиц
        create_tables_sql = """
        -- Таблица пользователей
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            is_subscribed BOOLEAN DEFAULT FALSE,
            subscription_end TIMESTAMP,
            free_requests_used INTEGER DEFAULT 0,
            is_admin BOOLEAN DEFAULT FALSE,
            is_super_admin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_payment_date TIMESTAMP,
            payment_provider VARCHAR(50)
        );
        
        -- Таблица платежей
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            payment_id VARCHAR(255) UNIQUE,
            amount INTEGER NOT NULL,
            currency VARCHAR(10) DEFAULT 'RUB',
            status VARCHAR(50) DEFAULT 'pending',
            invoice_payload TEXT,
            subscription_months INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cancellation_reason TEXT
        );
        
        -- Таблица запросов пользователей
        CREATE TABLE IF NOT EXISTS user_requests (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            request_type VARCHAR(100),
            request_data JSONB,
            response_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Таблица рассылок
        CREATE TABLE IF NOT EXISTS broadcast_messages (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            target_type VARCHAR(50) DEFAULT 'all',
            status VARCHAR(50) DEFAULT 'draft',
            scheduled_at TIMESTAMP,
            sent_at TIMESTAMP,
            total_sent INTEGER DEFAULT 0,
            total_delivered INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0,
            created_by BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Таблица обратной связи
        CREATE TABLE IF NOT EXISTS user_feedback (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            feedback_type VARCHAR(50),
            content TEXT,
            rating INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Таблица кэша поиска каналов
        CREATE TABLE IF NOT EXISTS channel_search_cache (
            id SERIAL PRIMARY KEY,
            search_query VARCHAR(255),
            results JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        );
        
        -- Таблица системных настроек
        CREATE TABLE IF NOT EXISTS system_settings (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        await conn.execute(create_tables_sql)
        logger.info("✅ Все таблицы созданы")
    
    async def _run_incremental_migrations(self, conn: asyncpg.Connection, existing_tables: List[str]):
        """Выполнение инкрементальных миграций"""
        logger.info("🔄 Выполнение инкрементальных миграций...")
        
        # Список всех необходимых таблиц
        required_tables = {
            'users', 'payments', 'user_requests', 'broadcast_messages',
            'user_feedback', 'channel_search_cache', 'system_settings'
        }
        
        # Создаем недостающие таблицы
        missing_tables = required_tables - set(existing_tables)
        
        if missing_tables:
            logger.info(f"📋 Создание недостающих таблиц: {', '.join(missing_tables)}")
            await self._run_full_initialization(conn)
        
        # Выполняем обновления схемы
        await self._update_table_schemas(conn, existing_tables)
    
    async def _update_table_schemas(self, conn: asyncpg.Connection, existing_tables: List[str]):
        """Обновление схем существующих таблиц"""
        logger.info("🔄 Обновление схем таблиц...")
        
        # Обновления схемы
        schema_updates = [
            {
                'table': 'users',
                'column': 'payment_provider',
                'definition': 'VARCHAR(50)',
                'default': 'NULL'
            },
            {
                'table': 'payments',
                'column': 'cancellation_reason',
                'definition': 'TEXT',
                'default': 'NULL'
            },
            {
                'table': 'payments',
                'column': 'updated_at',
                'definition': 'TIMESTAMP',
                'default': 'CURRENT_TIMESTAMP'
            }
        ]
        
        for update in schema_updates:
            if update['table'] in existing_tables:
                try:
                    # Проверяем существование колонки
                    check_query = """
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = $1 AND column_name = $2
                    """
                    
                    result = await conn.fetchval(check_query, update['table'], update['column'])
                    
                    if not result:
                        # Добавляем колонку
                        alter_query = f"""
                            ALTER TABLE {update['table']} 
                            ADD COLUMN {update['column']} {update['definition']} DEFAULT {update['default']}
                        """
                        await conn.execute(alter_query)
                        logger.info(f"✅ Добавлена колонка {update['column']} в таблицу {update['table']}")
                        
                except Exception as e:
                    logger.warning(f"Не удалось обновить таблицу {update['table']}: {e}")
    
    async def _create_performance_indexes(self, conn: asyncpg.Connection):
        """Создание индексов для производительности"""
        logger.info("🔄 Создание индексов для производительности...")
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(is_subscribed, subscription_end)",
            "CREATE INDEX IF NOT EXISTS idx_users_admin ON users(is_admin, is_super_admin)",
            "CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_requests_user_date ON user_requests(user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_broadcast_status ON broadcast_messages(status, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_cache_expires ON channel_search_cache(expires_at)"
        ]
        
        for index_sql in indexes:
            try:
                await conn.execute(index_sql)
            except Exception as e:
                logger.warning(f"Не удалось создать индекс: {e}")
        
        logger.info("✅ Индексы созданы")
    
    async def _update_system_settings(self, conn: asyncpg.Connection):
        """Обновление системных настроек"""
        try:
            settings = [
                ('database_version', '2.0.0', 'Версия базы данных'),
                ('last_migration', datetime.now().isoformat(), 'Дата последней миграции'),
                ('production_mode', 'true', 'Режим production'),
                ('migration_status', 'completed', 'Статус миграций'),
                ('deployment_platform', 'railpack_dokploy', 'Платформа деплоя')
            ]
            
            for key, value, description in settings:
                query = """
                    INSERT INTO system_settings (key, value, description, updated_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = CURRENT_TIMESTAMP
                """
                await conn.execute(query, key, value, description)
            
            logger.info("✅ Системные настройки обновлены")
            
        except Exception as e:
            logger.warning(f"Не удалось обновить системные настройки: {e}")
    
    async def optimize_for_production(self):
        """Оптимизация базы данных для production"""
        try:
            logger.info("🔧 Оптимизация базы данных для production...")
            
            if not self.connection_pool:
                await self.verify_connection()
            
            async with self.connection_pool.acquire() as conn:
                # Анализируем таблицы для оптимизации запросов
                await conn.execute("ANALYZE")
                
                # Обновляем статистику
                await conn.execute("VACUUM ANALYZE")
            
            logger.info("✅ База данных оптимизирована для production")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при оптимизации базы данных: {e}")
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Получить статистику базы данных"""
        try:
            if not self.connection_pool:
                await self.verify_connection()
            
            async with self.connection_pool.acquire() as conn:
                stats = {}
                
                # Размер базы данных
                db_size = await conn.fetchval("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """)
                stats['database_size'] = db_size
                
                # Количество записей в таблицах
                tables = ['users', 'payments', 'user_requests', 'broadcast_messages']
                for table in tables:
                    try:
                        count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                        stats[f'{table}_count'] = count
                    except:
                        stats[f'{table}_count'] = 0
                
                # Активные подписки
                active_subs = await conn.fetchval("""
                    SELECT COUNT(*) FROM users 
                    WHERE is_subscribed = TRUE 
                    AND (subscription_end IS NULL OR subscription_end > NOW())
                """)
                stats['active_subscriptions'] = active_subs
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Ошибка при получении статистики БД: {e}")
            return {}
    
    async def close(self):
        """Закрытие пула соединений"""
        if self.connection_pool:
            await self.connection_pool.close()
            logger.info("✅ Пул соединений PostgreSQL закрыт")
