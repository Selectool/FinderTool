"""
Универсальный адаптер базы данных для SQLite и PostgreSQL
"""
import os
import asyncio
import logging
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class DatabaseAdapter:
    """Универсальный адаптер для работы с SQLite и PostgreSQL"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.db_type = self._detect_db_type(database_url)
        self.connection = None
        
    def _detect_db_type(self, url: str) -> str:
        """Определить тип базы данных по URL"""
        if url.startswith('sqlite'):
            return 'sqlite'
        elif url.startswith('postgresql') or url.startswith('postgres'):
            return 'postgresql'
        else:
            # По умолчанию SQLite для локальной разработки
            return 'sqlite'
    
    async def connect(self):
        """Установить соединение с базой данных"""
        if self.db_type == 'sqlite':
            import aiosqlite
            # Извлекаем путь к файлу из URL
            if self.database_url.startswith('sqlite:///'):
                db_path = self.database_url[10:]  # Убираем 'sqlite:///'
            else:
                db_path = self.database_url.replace('sqlite://', '')
            self.connection = await aiosqlite.connect(db_path)
            self.connection.row_factory = aiosqlite.Row
            
        elif self.db_type == 'postgresql':
            import asyncpg
            self.connection = await asyncpg.connect(self.database_url)
            
    async def disconnect(self):
        """Закрыть соединение с базой данных"""
        if self.connection:
            await self.connection.close()
            
    async def execute(self, query: str, params: tuple = None) -> Any:
        """Выполнить SQL запрос"""
        if not self.connection:
            await self.connect()
            
        if self.db_type == 'sqlite':
            if params:
                cursor = await self.connection.execute(query, params)
            else:
                cursor = await self.connection.execute(query)
            await self.connection.commit()
            return cursor
            
        elif self.db_type == 'postgresql':
            if params:
                # Конвертируем ? в $1, $2, etc для PostgreSQL
                pg_query = self._convert_query_to_pg(query)
                return await self.connection.execute(pg_query, *params)
            else:
                return await self.connection.execute(query)
    
    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Получить одну запись"""
        if not self.connection:
            await self.connect()
            
        if self.db_type == 'sqlite':
            if params:
                cursor = await self.connection.execute(query, params)
            else:
                cursor = await self.connection.execute(query)
            row = await cursor.fetchone()
            return dict(row) if row else None
            
        elif self.db_type == 'postgresql':
            if params:
                pg_query = self._convert_query_to_pg(query)
                row = await self.connection.fetchrow(pg_query, *params)
            else:
                row = await self.connection.fetchrow(query)
            return dict(row) if row else None
    
    async def fetch_all(self, query: str, params: tuple = None) -> List[Dict]:
        """Получить все записи"""
        if not self.connection:
            await self.connect()
            
        if self.db_type == 'sqlite':
            if params:
                cursor = await self.connection.execute(query, params)
            else:
                cursor = await self.connection.execute(query)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        elif self.db_type == 'postgresql':
            if params:
                pg_query = self._convert_query_to_pg(query)
                rows = await self.connection.fetch(pg_query, *params)
            else:
                rows = await self.connection.fetch(query)
            return [dict(row) for row in rows]
    
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
        """Получить SQL для создания таблиц"""
        if self.db_type == 'sqlite':
            return self._get_sqlite_tables()
        elif self.db_type == 'postgresql':
            return self._get_postgresql_tables()
    
    def _get_sqlite_tables(self) -> List[str]:
        """SQL для создания таблиц SQLite"""
        return [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                requests_used INTEGER DEFAULT 0,
                is_subscribed BOOLEAN DEFAULT FALSE,
                subscription_end TIMESTAMP,
                last_request TIMESTAMP,
                last_payment_date TIMESTAMP,
                payment_provider TEXT,
                role TEXT DEFAULT 'user',
                blocked BOOLEAN DEFAULT FALSE,
                bot_blocked BOOLEAN DEFAULT FALSE,
                blocked_at TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channels_input TEXT,
                results TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                payment_id TEXT UNIQUE,
                provider_payment_id TEXT,
                amount INTEGER,
                currency TEXT DEFAULT 'RUB',
                status TEXT DEFAULT 'pending',
                invoice_payload TEXT,
                subscription_months INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """
        ]
    
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
