"""
Универсальный класс базы данных для работы с PostgreSQL и SQLite
Заменяет старый Database класс с поддержкой production-ready функций
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from .db_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class UniversalDatabase:
    """Универсальный класс для работы с базой данных через DatabaseAdapter"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv('DATABASE_URL', 'sqlite:///bot.db')
        self.adapter = DatabaseAdapter(self.database_url)
        
        # Для совместимости с существующим кодом
        self.db_path = "bot.db"  # Legacy поддержка
        
    async def get_user(self, user_id: int) -> Optional[dict]:
        """Получить пользователя"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = "SELECT * FROM users WHERE user_id = ?"
                params = (user_id,)
            else:  # PostgreSQL
                query = "SELECT * FROM users WHERE user_id = $1"
                params = (user_id,)
            
            result = await self.adapter.fetch_one(query, params)
            await self.adapter.disconnect()
            
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователя {user_id}: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return None
    
    async def create_user(self, user_id: int, username: str = None,
                         first_name: str = None, last_name: str = None, role: str = None):
        """Создать пользователя"""
        try:
            from bot.utils.roles import TelegramUserPermissions
            
            # Определяем роль пользователя
            if role is None:
                role = TelegramUserPermissions.get_user_role(user_id)
            
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT OR REPLACE INTO users
                    (user_id, username, first_name, last_name, created_at, role)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (user_id, username, first_name, last_name, datetime.now(), role)
            else:  # PostgreSQL
                query = """
                    INSERT INTO users
                    (user_id, username, first_name, last_name, created_at, role)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        role = EXCLUDED.role
                """
                params = (user_id, username, first_name, last_name, datetime.now(), role)
            
            await self.adapter.execute(query, params)
            await self.adapter.disconnect()
            
        except Exception as e:
            logger.error(f"Ошибка создания пользователя {user_id}: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
    
    async def check_subscription(self, user_id: int) -> bool:
        """Проверить активность подписки"""
        try:
            user = await self.get_user(user_id)
            if not user:
                return False
            
            # Проверяем is_subscribed
            is_subscribed = user.get('is_subscribed', False)
            if not is_subscribed:
                return False
            
            # Проверяем дату окончания подписки
            subscription_end = user.get('subscription_end')
            if subscription_end:
                if isinstance(subscription_end, str):
                    end_date = datetime.fromisoformat(subscription_end.replace('Z', '+00:00'))
                else:
                    end_date = subscription_end
                return datetime.now() < end_date
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка проверки подписки для {user_id}: {e}")
            return False
    
    async def subscribe_user(self, user_id: int, months: int = 1, provider: str = "yookassa"):
        """Оформить подписку пользователю"""
        try:
            end_date = datetime.now() + timedelta(days=30 * months)
            
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    UPDATE users
                    SET is_subscribed = TRUE, subscription_end = ?,
                        last_payment_date = ?, payment_provider = ?
                    WHERE user_id = ?
                """
                params = (end_date, datetime.now(), provider, user_id)
            else:  # PostgreSQL
                query = """
                    UPDATE users
                    SET is_subscribed = TRUE, subscription_end = $1,
                        last_payment_date = $2, payment_provider = $3
                    WHERE user_id = $4
                """
                params = (end_date, datetime.now(), provider, user_id)
            
            await self.adapter.execute(query, params)
            await self.adapter.disconnect()
            
        except Exception as e:
            logger.error(f"Ошибка оформления подписки для {user_id}: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
    
    async def update_user_requests(self, user_id: int):
        """Увеличить счетчик запросов пользователя"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    UPDATE users 
                    SET requests_used = requests_used + 1, last_request = ?
                    WHERE user_id = ?
                """
                params = (datetime.now(), user_id)
            else:  # PostgreSQL
                # В PostgreSQL колонка называется last_activity
                query = """
                    UPDATE users
                    SET requests_used = requests_used + 1, last_activity = $1
                    WHERE user_id = $2
                """
                params = (datetime.now(), user_id)
            
            await self.adapter.execute(query, params)
            await self.adapter.disconnect()
            
        except Exception as e:
            logger.error(f"Ошибка обновления запросов для {user_id}: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
    
    async def can_make_request(self, user_id: int, free_limit: int = 3) -> bool:
        """Проверить, может ли пользователь сделать запрос"""
        try:
            from bot.utils.roles import TelegramUserPermissions

            user = await self.get_user(user_id)
            if not user:
                return True  # Новый пользователь

            # Проверяем блокировку администратором
            if user.get('blocked', False):
                return False

            # Проверяем, заблокировал ли пользователь бота
            if user.get('bot_blocked', False):
                return False

            # Проверяем роль пользователя - администраторы имеют безлимитный доступ
            user_role = user.get('role', 'user')
            if TelegramUserPermissions.has_unlimited_access(user_id, user_role):
                return True

            # Проверяем подписку
            if await self.check_subscription(user_id):
                return True

            # Проверяем лимит бесплатных запросов
            requests_used = user.get('requests_used', 0)
            return requests_used < free_limit
            
        except Exception as e:
            logger.error(f"Ошибка проверки возможности запроса для {user_id}: {e}")
            return False
    
    async def save_request(self, user_id: int, channels_input: List[str], results: List[dict]):
        """Сохранить запрос в базу"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO requests (user_id, channels_input, results)
                    VALUES (?, ?, ?)
                """
                params = (user_id, json.dumps(channels_input), json.dumps(results))
            else:  # PostgreSQL
                query = """
                    INSERT INTO requests (user_id, channels_input, results)
                    VALUES ($1, $2, $3)
                """
                params = (user_id, json.dumps(channels_input), json.dumps(results))
            
            await self.adapter.execute(query, params)
            await self.adapter.disconnect()
            
        except Exception as e:
            logger.error(f"Ошибка сохранения запроса для {user_id}: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
    
    async def get_stats(self) -> Dict[str, Any]:
        """Получить статистику"""
        try:
            await self.adapter.connect()
            
            stats = {}
            
            # Общее количество пользователей
            total_users_result = await self.adapter.fetch_one("SELECT COUNT(*) FROM users")
            stats['total_users'] = total_users_result[0] if total_users_result else 0
            
            # Активные подписчики
            if self.adapter.db_type == 'sqlite':
                active_subs_query = """
                    SELECT COUNT(*) FROM users 
                    WHERE is_subscribed = 1 
                    AND (subscription_end IS NULL OR subscription_end > datetime('now'))
                """
            else:  # PostgreSQL
                active_subs_query = """
                    SELECT COUNT(*) FROM users 
                    WHERE is_subscribed = TRUE 
                    AND (subscription_end IS NULL OR subscription_end > NOW())
                """
            
            active_subs_result = await self.adapter.fetch_one(active_subs_query)
            stats['active_subscribers'] = active_subs_result[0] if active_subs_result else 0
            
            # Запросы за сегодня
            if self.adapter.db_type == 'sqlite':
                requests_today_query = """
                    SELECT COUNT(*) FROM requests 
                    WHERE created_at >= date('now')
                """
            else:  # PostgreSQL
                requests_today_query = """
                    SELECT COUNT(*) FROM requests 
                    WHERE created_at >= CURRENT_DATE
                """
            
            requests_today_result = await self.adapter.fetch_one(requests_today_query)
            stats['requests_today'] = requests_today_result[0] if requests_today_result else 0
            
            await self.adapter.disconnect()
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return {'total_users': 0, 'active_subscribers': 0, 'requests_today': 0}
    
    async def get_user_role(self, user_id: int) -> str:
        """Получить роль пользователя"""
        try:
            from bot.utils.roles import TelegramUserPermissions

            user = await self.get_user(user_id)
            if user and 'role' in user:
                return user['role']

            # Возвращаем роль по умолчанию или предопределенную
            return TelegramUserPermissions.get_user_role(user_id)

        except Exception as e:
            logger.error(f"Ошибка получения роли для {user_id}: {e}")
            return 'user'

    # ========== ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ ДЛЯ СОВМЕСТИМОСТИ ==========

    async def get_users_count(self) -> int:
        """Получить общее количество пользователей"""
        try:
            await self.adapter.connect()
            result = await self.adapter.fetch_one("SELECT COUNT(*) FROM users")
            await self.adapter.disconnect()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Ошибка получения количества пользователей: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return 0

    async def get_subscribers_count(self) -> int:
        """Получить количество активных подписчиков"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT COUNT(*) FROM users
                    WHERE is_subscribed = 1
                    AND (subscription_end IS NULL OR subscription_end > datetime('now'))
                """
            else:  # PostgreSQL
                query = """
                    SELECT COUNT(*) FROM users
                    WHERE is_subscribed = TRUE
                    AND (subscription_end IS NULL OR subscription_end > NOW())
                """

            result = await self.adapter.fetch_one(query)
            await self.adapter.disconnect()
            return result[0] if result else 0

        except Exception as e:
            logger.error(f"Ошибка получения количества подписчиков: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return 0

    async def get_total_requests_count(self) -> int:
        """Получить общее количество запросов"""
        try:
            await self.adapter.connect()
            result = await self.adapter.fetch_one("SELECT COUNT(*) FROM requests")
            await self.adapter.disconnect()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Ошибка получения количества запросов: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return 0

    async def get_active_users_count(self) -> int:
        """Получить количество активных пользователей (за последние 30 дней)"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT COUNT(*) FROM users
                    WHERE last_request > datetime('now', '-30 days')
                """
            else:  # PostgreSQL
                # В PostgreSQL колонка называется last_activity
                query = """
                    SELECT COUNT(*) FROM users
                    WHERE last_activity > NOW() - INTERVAL '30 days'
                """

            result = await self.adapter.fetch_one(query)
            await self.adapter.disconnect()
            return result[0] if result else 0

        except Exception as e:
            logger.error(f"Ошибка получения количества активных пользователей: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return 0

    async def get_all_users_for_broadcast(self) -> List[dict]:
        """Получить всех пользователей для рассылки"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = "SELECT user_id FROM users"
            else:  # PostgreSQL
                query = "SELECT user_id FROM users"

            results = await self.adapter.fetch_all(query)
            await self.adapter.disconnect()

            return [{'user_id': row[0]} for row in results] if results else []

        except Exception as e:
            logger.error(f"Ошибка получения пользователей для рассылки: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return []

    async def get_active_users_for_broadcast(self, days: int = 30) -> List[dict]:
        """Получить активных пользователей для рассылки"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = f"""
                    SELECT user_id FROM users
                    WHERE last_request > datetime('now', '-{days} days')
                """
            else:  # PostgreSQL
                # В PostgreSQL колонка называется last_activity
                query = f"""
                    SELECT user_id FROM users
                    WHERE last_activity > NOW() - INTERVAL '{days} days'
                """

            results = await self.adapter.fetch_all(query)
            await self.adapter.disconnect()

            return [{'user_id': row[0]} for row in results] if results else []

        except Exception as e:
            logger.error(f"Ошибка получения активных пользователей для рассылки: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return []

    async def get_subscribed_users(self) -> List[dict]:
        """Получить всех подписчиков для рассылки"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT user_id FROM users
                    WHERE is_subscribed = 1
                    AND (subscription_end IS NULL OR subscription_end > datetime('now'))
                """
            else:  # PostgreSQL
                query = """
                    SELECT user_id FROM users
                    WHERE is_subscribed = TRUE
                    AND (subscription_end IS NULL OR subscription_end > NOW())
                """

            results = await self.adapter.fetch_all(query)
            await self.adapter.disconnect()

            return [{'user_id': row[0]} for row in results] if results else []

        except Exception as e:
            logger.error(f"Ошибка получения подписчиков для рассылки: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return []

    # ========== МЕТОДЫ ДЛЯ РАССЫЛОК ==========

    async def create_broadcast(self, title: str, message: str, target_users: str = "all",
                              scheduled_time: datetime = None, created_by: int = None) -> int:
        """Создать рассылку"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO broadcasts
                    (title, message, target_users, scheduled_time, created_by, created_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """
                params = (title, message, target_users, scheduled_time, created_by, datetime.now())
            else:  # PostgreSQL
                query = """
                    INSERT INTO broadcasts
                    (title, message, target_users, scheduled_time, created_by, created_at, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'pending')
                    RETURNING id
                """
                params = (title, message, target_users, scheduled_time, created_by, datetime.now())

            if self.adapter.db_type == 'postgresql':
                result = await self.adapter.fetch_one(query, params)
                broadcast_id = result[0] if result else None
            else:
                await self.adapter.execute(query, params)
                # Для SQLite получаем последний ID
                result = await self.adapter.fetch_one("SELECT last_insert_rowid()")
                broadcast_id = result[0] if result else None

            await self.adapter.disconnect()
            return broadcast_id

        except Exception as e:
            logger.error(f"Ошибка создания рассылки: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return None

    async def update_user_activity(self, user_id: int):
        """Обновить время последней активности пользователя"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    UPDATE users
                    SET last_request = ?
                    WHERE user_id = ?
                """
                params = (datetime.now(), user_id)
            else:  # PostgreSQL
                query = """
                    UPDATE users
                    SET last_activity = $1
                    WHERE user_id = $2
                """
                params = (datetime.now(), user_id)

            await self.adapter.execute(query, params)
            await self.adapter.disconnect()

        except Exception as e:
            logger.error(f"Ошибка обновления активности для {user_id}: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
