"""
PostgreSQL адаптер базы данных
"""
import os
import asyncio
import logging
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class DatabaseAdapter:
    """Production-ready PostgreSQL адаптер с connection pooling"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.db_type = 'postgresql'  # Только PostgreSQL
        self.connection = None
        self.connection_pool = None
        self._connection_retries = 3
        self._connection_timeout = 30

        if not (database_url.startswith('postgresql://') or database_url.startswith('postgres://')):
            raise ValueError("Поддерживается только PostgreSQL. DATABASE_URL должен начинаться с 'postgresql://' или 'postgres://'")

        logger.debug(f"Инициализирован PostgreSQL адаптер")

    async def connect(self):
        """Установить соединение с PostgreSQL с retry логикой"""
        import asyncpg

        for attempt in range(self._connection_retries):
            try:
                if self.connection and not self.connection.is_closed():
                    return  # Соединение уже активно

                self.connection = await asyncpg.connect(
                    self.database_url,
                    command_timeout=self._connection_timeout
                )
                logger.debug(f"✅ PostgreSQL соединение установлено (попытка {attempt + 1})")
                return

            except Exception as e:
                logger.warning(f"⚠️ Ошибка подключения к PostgreSQL (попытка {attempt + 1}/{self._connection_retries}): {e}")
                if attempt == self._connection_retries - 1:
                    logger.error(f"❌ Не удалось подключиться к PostgreSQL после {self._connection_retries} попыток")
                    raise
                await asyncio.sleep(1)  # Пауза перед повторной попыткой

    async def disconnect(self):
        """Закрыть соединение с базой данных"""
        try:
            if self.connection and not self.connection.is_closed():
                await self.connection.close()
                logger.debug("✅ PostgreSQL соединение закрыто")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при закрытии соединения: {e}")
        finally:
            self.connection = None
            
    async def _ensure_connection(self):
        """Убедиться, что соединение активно"""
        if not self.connection or self.connection.is_closed():
            await self.connect()

    async def execute(self, query: str, params: tuple = None) -> Any:
        """Выполнить SQL запрос в PostgreSQL с автоматическим переподключением"""
        await self._ensure_connection()

        try:
            if params:
                # Конвертируем ? в $1, $2, etc для PostgreSQL
                pg_query = self._convert_query_to_pg(query)
                return await self.connection.execute(pg_query, *params)
            else:
                return await self.connection.execute(query)
        except Exception as e:
            if "connection" in str(e).lower() or "closed" in str(e).lower():
                logger.warning(f"⚠️ Соединение потеряно, переподключаемся: {e}")
                await self.connect()
                # Повторяем запрос
                if params:
                    pg_query = self._convert_query_to_pg(query)
                    return await self.connection.execute(pg_query, *params)
                else:
                    return await self.connection.execute(query)
            raise
    
    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Получить одну запись из PostgreSQL с автоматическим переподключением"""
        await self._ensure_connection()

        try:
            if params:
                pg_query = self._convert_query_to_pg(query)
                row = await self.connection.fetchrow(pg_query, *params)
            else:
                row = await self.connection.fetchrow(query)
            return dict(row) if row else None
        except Exception as e:
            if "connection" in str(e).lower() or "closed" in str(e).lower():
                logger.warning(f"⚠️ Соединение потеряно при fetch_one, переподключаемся: {e}")
                await self.connect()
                # Повторяем запрос
                if params:
                    pg_query = self._convert_query_to_pg(query)
                    row = await self.connection.fetchrow(pg_query, *params)
                else:
                    row = await self.connection.fetchrow(query)
                return dict(row) if row else None
            raise

    async def fetch_all(self, query: str, params: tuple = None) -> List[Dict]:
        """Получить все записи из PostgreSQL с автоматическим переподключением"""
        await self._ensure_connection()

        try:
            if params:
                pg_query = self._convert_query_to_pg(query)
                rows = await self.connection.fetch(pg_query, *params)
            else:
                rows = await self.connection.fetch(query)
            return [dict(row) for row in rows]
        except Exception as e:
            if "connection" in str(e).lower() or "closed" in str(e).lower():
                logger.warning(f"⚠️ Соединение потеряно при fetch_all, переподключаемся: {e}")
                await self.connect()
                # Повторяем запрос
                if params:
                    pg_query = self._convert_query_to_pg(query)
                    rows = await self.connection.fetch(pg_query, *params)
                else:
                    rows = await self.connection.fetch(query)
                return [dict(row) for row in rows]
            raise
    
    def _convert_query_to_pg(self, query: str) -> str:
        """Конвертировать SQLite запрос в PostgreSQL формат"""
        # Заменяем ? на $1, $2, etc
        pg_query = query
        param_count = 1
        while '?' in pg_query:
            pg_query = pg_query.replace('?', f'${param_count}', 1)
            param_count += 1
        
        # Заменяем SQLite специфичные функции
        replacements = {
            'datetime(\'now\')': 'NOW()',
            'datetime(\'now\', \'-30 days\')': 'NOW() - INTERVAL \'30 days\'',
            'DATE(created_at)': 'DATE(created_at)',
            'PRAGMA table_info': 'SELECT column_name FROM information_schema.columns WHERE table_name =',
            'sqlite_master': 'information_schema.tables',
        }
        
        for sqlite_func, pg_func in replacements.items():
            pg_query = pg_query.replace(sqlite_func, pg_func)
            
        return pg_query
    
    async def create_tables_if_not_exist(self):
        """Создать таблицы если они не существуют"""
        tables_sql = self._get_create_tables_sql()
        
        for table_sql in tables_sql:
            try:
                await self.execute(table_sql)
                logger.info(f"Таблица создана или уже существует")
            except Exception as e:
                logger.error(f"Ошибка создания таблицы: {e}")
    
    def _get_create_tables_sql(self) -> List[str]:
        """Получить SQL для создания таблиц PostgreSQL"""
        return self._get_postgresql_tables()
    
    def _get_postgresql_tables(self) -> List[str]:
        """SQL для создания таблиц PostgreSQL"""
        return [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                requests_used INTEGER DEFAULT 0,
                is_subscribed BOOLEAN DEFAULT FALSE,
                subscription_end TIMESTAMP,
                last_request TIMESTAMP,
                last_payment_date TIMESTAMP,
                payment_provider TEXT,
                role TEXT DEFAULT 'user',
                unlimited_access BOOLEAN DEFAULT FALSE,
                blocked BOOLEAN DEFAULT FALSE,
                bot_blocked BOOLEAN DEFAULT FALSE,
                blocked_at TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS requests (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                channels_input TEXT,
                results TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                payment_id TEXT UNIQUE,
                provider_payment_id TEXT,
                amount INTEGER,
                currency TEXT DEFAULT 'RUB',
                status TEXT DEFAULT 'pending',
                invoice_payload TEXT,
                subscription_months INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """
        ]


# Глобальная переменная для хранения экземпляра адаптера
_database_adapter: Optional[DatabaseAdapter] = None


def get_database() -> Optional[DatabaseAdapter]:
    """Получить глобальный экземпляр адаптера базы данных"""
    return _database_adapter


def set_database(adapter: DatabaseAdapter):
    """Установить глобальный экземпляр адаптера базы данных"""
    global _database_adapter
    _database_adapter = adapter
