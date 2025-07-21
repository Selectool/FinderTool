"""
Модели базы данных
"""
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List
import json


class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path

    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    requests_used INTEGER DEFAULT 0,
                    is_subscribed BOOLEAN DEFAULT FALSE,
                    subscription_end TIMESTAMP,
                    last_request TIMESTAMP
                )
            """)
            
            # Таблица запросов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    channels_input TEXT,
                    results TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Таблица рассылок
            await db.execute("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_text TEXT,
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed BOOLEAN DEFAULT FALSE
                )
            """)
            
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[dict]:
        """Получить пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_user(self, user_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None):
        """Создать пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, datetime.now()))
            await db.commit()

    async def update_user_requests(self, user_id: int):
        """Увеличить счетчик запросов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET requests_used = requests_used + 1, last_request = ?
                WHERE user_id = ?
            """, (datetime.now(), user_id))
            await db.commit()

    async def subscribe_user(self, user_id: int, months: int = 1):
        """Оформить подписку пользователю"""
        end_date = datetime.now() + timedelta(days=30 * months)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET is_subscribed = TRUE, subscription_end = ?
                WHERE user_id = ?
            """, (end_date, user_id))
            await db.commit()

    async def check_subscription(self, user_id: int) -> bool:
        """Проверить активность подписки"""
        user = await self.get_user(user_id)
        if not user or not user['is_subscribed']:
            return False
        
        if user['subscription_end']:
            end_date = datetime.fromisoformat(user['subscription_end'])
            return datetime.now() < end_date
        return False

    async def can_make_request(self, user_id: int, free_limit: int = 3) -> bool:
        """Проверить, может ли пользователь сделать запрос"""
        user = await self.get_user(user_id)
        if not user:
            return True  # Новый пользователь
        
        # Проверяем подписку
        if await self.check_subscription(user_id):
            return True
        
        # Проверяем лимит бесплатных запросов
        return user['requests_used'] < free_limit

    async def save_request(self, user_id: int, channels_input: List[str], 
                          results: List[dict]):
        """Сохранить запрос в базу"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO requests (user_id, channels_input, results)
                VALUES (?, ?, ?)
            """, (user_id, json.dumps(channels_input), json.dumps(results)))
            await db.commit()

    async def get_all_users(self) -> List[dict]:
        """Получить всех пользователей для рассылки"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT user_id FROM users")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_stats(self) -> dict:
        """Получить статистику бота"""
        async with aiosqlite.connect(self.db_path) as db:
            # Общее количество пользователей
            cursor = await db.execute("SELECT COUNT(*) as total FROM users")
            total_users = (await cursor.fetchone())[0]
            
            # Активные подписчики
            cursor = await db.execute("""
                SELECT COUNT(*) as active FROM users 
                WHERE is_subscribed = TRUE AND subscription_end > ?
            """, (datetime.now(),))
            active_subscribers = (await cursor.fetchone())[0]
            
            # Запросы за сегодня
            today = datetime.now().date()
            cursor = await db.execute("""
                SELECT COUNT(*) as today FROM requests 
                WHERE DATE(created_at) = ?
            """, (today,))
            requests_today = (await cursor.fetchone())[0]
            
            return {
                'total_users': total_users,
                'active_subscribers': active_subscribers,
                'requests_today': requests_today
            }
