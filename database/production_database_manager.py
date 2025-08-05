"""
Production-ready менеджер базы данных
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ProductionDatabaseManager:
    """Production-ready менеджер базы данных"""
    
    def __init__(self):
        self.database_url = None
        self.database_type = None
        self.connection_pool = None
        self.is_initialized = False
        self.tables_created = []
    
    async def initialize_database(self, database_url: str) -> Dict[str, Any]:
        """Инициализация production базы данных"""
        try:
            self.database_url = database_url
            
            # Определяем тип базы данных
            if database_url.startswith(('postgresql://', 'postgres://')):
                self.database_type = 'postgresql'
                return await self._initialize_postgresql()
            else:
                raise ValueError("Поддерживается только PostgreSQL")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    async def _initialize_postgresql(self) -> Dict[str, Any]:
        """Инициализация PostgreSQL"""
        try:
            import asyncpg
            
            # Создаем пул соединений
            self.connection_pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=10,
                command_timeout=30
            )
            
            # Проверяем подключение
            async with self.connection_pool.acquire() as conn:
                version = await conn.fetchval('SELECT version()')
                logger.info(f"✅ PostgreSQL подключение успешно: {version}")
            
            # Создаем базовые таблицы
            await self._create_base_tables()
            
            self.is_initialized = True
            
            return {
                'database_type': 'postgresql',
                'status': 'initialized',
                'tables': self.tables_created,
                'pool_size': len(self.connection_pool._holders) if self.connection_pool else 0,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка инициализации PostgreSQL: {e}")
            raise
    
    async def _create_base_tables(self):
        """Создание базовых таблиц"""
        try:
            async with self.connection_pool.acquire() as conn:
                # Таблица пользователей (используем user_id как в остальной системе)
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        language_code VARCHAR(10),
                        is_bot BOOLEAN DEFAULT FALSE,
                        is_premium BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        subscription_until TIMESTAMP,
                        requests_count INTEGER DEFAULT 0,
                        role VARCHAR(50) DEFAULT 'user'
                    )
                ''')
                self.tables_created.append('users')
                
                # Таблица запросов (исправляем внешний ключ)
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_requests (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(user_id),
                        request_type VARCHAR(100),
                        request_data TEXT,
                        response_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processing_time FLOAT,
                        status VARCHAR(50) DEFAULT 'completed'
                    )
                ''')
                self.tables_created.append('user_requests')
                
                # Таблица платежей (исправляем внешний ключ)
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS payments (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(user_id),
                        payment_id VARCHAR(255) UNIQUE,
                        amount DECIMAL(10,2),
                        currency VARCHAR(10) DEFAULT 'RUB',
                        status VARCHAR(50),
                        payment_method VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB
                    )
                ''')
                self.tables_created.append('payments')
                
                # Таблица рассылок
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS broadcasts (
                        id SERIAL PRIMARY KEY,
                        admin_id BIGINT,
                        message_text TEXT,
                        target_audience VARCHAR(50),
                        total_users INTEGER DEFAULT 0,
                        sent_count INTEGER DEFAULT 0,
                        failed_count INTEGER DEFAULT 0,
                        status VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                ''')
                self.tables_created.append('broadcasts')
                
                # Индексы для оптимизации
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(subscription_until)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_requests_user_id ON user_requests(user_id)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_requests_created_at ON user_requests(created_at)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)')
                
                logger.info(f"✅ Создано таблиц: {len(self.tables_created)}")
                
        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка состояния базы данных"""
        try:
            if not self.connection_pool:
                return {
                    'status': 'unhealthy',
                    'message': 'Connection pool not initialized',
                    'timestamp': datetime.now().isoformat()
                }
            
            async with self.connection_pool.acquire() as conn:
                # Простая проверка
                result = await conn.fetchval('SELECT 1')
                
                # Проверка количества соединений
                pool_info = {
                    'size': self.connection_pool.get_size(),
                    'min_size': self.connection_pool.get_min_size(),
                    'max_size': self.connection_pool.get_max_size(),
                }
                
                return {
                    'status': 'healthy',
                    'database_type': self.database_type,
                    'pool_info': pool_info,
                    'tables_count': len(self.tables_created),
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_connection(self):
        """Получить соединение из пула"""
        if not self.connection_pool:
            raise RuntimeError("Database not initialized")
        return self.connection_pool.acquire()
    
    async def close(self):
        """Закрытие пула соединений"""
        if self.connection_pool:
            await self.connection_pool.close()
            logger.info("✅ Database connection pool closed")


# Глобальный экземпляр
production_db_manager = ProductionDatabaseManager()


async def initialize_production_database(database_url: str) -> Dict[str, Any]:
    """Инициализация production базы данных"""
    return await production_db_manager.initialize_database(database_url)


async def get_db_connection():
    """Получить соединение с базой данных"""
    return await production_db_manager.get_connection()


async def close_database():
    """Закрыть соединения с базой данных"""
    await production_db_manager.close()
