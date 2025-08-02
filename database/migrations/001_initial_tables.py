"""
Миграция 001: Создание базовых таблиц
Создана: 2025-08-02 22:30:00
"""
from database.migration_manager import Migration
from database.db_adapter import DatabaseAdapter

class Migration001(Migration):
    def __init__(self):
        super().__init__("001", "Создание базовых таблиц (users, broadcast_messages)")
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        # Таблица пользователей
        if adapter.db_type == 'sqlite':
            users_query = """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    language_code TEXT DEFAULT 'ru',
                    is_premium BOOLEAN DEFAULT FALSE,
                    subscription_active BOOLEAN DEFAULT FALSE,
                    subscription_end_date TIMESTAMP,
                    free_requests_used INTEGER DEFAULT 0,
                    total_requests INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        else:  # PostgreSQL
            users_query = """
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    language_code VARCHAR(10) DEFAULT 'ru',
                    is_premium BOOLEAN DEFAULT FALSE,
                    subscription_active BOOLEAN DEFAULT FALSE,
                    subscription_end_date TIMESTAMP,
                    free_requests_used INTEGER DEFAULT 0,
                    total_requests INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        
        await adapter.execute(users_query)
        
        # Таблица рассылок
        if adapter.db_type == 'sqlite':
            broadcasts_query = """
                CREATE TABLE IF NOT EXISTS broadcast_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """
        else:  # PostgreSQL
            broadcasts_query = """
                CREATE TABLE IF NOT EXISTS broadcast_messages (
                    id SERIAL PRIMARY KEY,
                    message TEXT NOT NULL,
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """
        
        await adapter.execute(broadcasts_query)
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        await adapter.execute("DROP TABLE IF EXISTS broadcast_messages")
        await adapter.execute("DROP TABLE IF EXISTS users")

# Экспортируем класс для менеджера миграций
Migration = Migration001
