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
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL обязательна! Укажите PostgreSQL URL в переменных окружения.")
        self.adapter = DatabaseAdapter(self.database_url)

    def _extract_count(self, result) -> int:
        """Извлечь значение COUNT из результата PostgreSQL"""
        if not result:
            return 0
        try:
            # PostgreSQL через DatabaseAdapter возвращает dict
            if isinstance(result, dict):
                # Ищем ключ count или первое значение
                if 'count' in result:
                    return int(result['count'])
                elif len(result) > 0:
                    # Берем первое значение
                    return int(list(result.values())[0])
            elif hasattr(result, '__getitem__'):
                # Если это Record или tuple-like объект
                return int(result[0])
            elif hasattr(result, 'values'):
                # Если это Record с методом values()
                values = list(result.values())
                return int(values[0]) if values else 0
            else:
                # Если это уже число
                return int(result)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            # Логируем для отладки
            logger.error(f"Ошибка извлечения count из {result} (тип: {type(result)}): {e}")
            return 0

    async def init_db(self):
        """Инициализация базы данных (для совместимости)"""
        # Этот метод нужен для совместимости с админ-панелью
        # В production используется ProductionDatabaseManager
        pass
        
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
            stats['total_users'] = self._extract_count(total_users_result)
            
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
            stats['active_subscribers'] = self._extract_count(active_subs_result)
            
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
            stats['requests_today'] = self._extract_count(requests_today_result)
            
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

            if result is not None:
                count = self._extract_count(result)

                # Преобразуем в int
                return int(count) if count is not None else 0
            return 0

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

            return self._extract_count(result)

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
            return self._extract_count(result)
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
            return self._extract_count(result)

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

            if results:
                user_list = []
                for row in results:
                    if isinstance(row, dict):
                        user_id = row.get('user_id')
                    elif hasattr(row, '__getitem__'):
                        user_id = row[0]
                    else:
                        user_id = getattr(row, 'user_id', None)

                    if user_id:
                        user_list.append({'user_id': user_id})
                return user_list
            return []

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

            if results:
                user_list = []
                for row in results:
                    if isinstance(row, dict):
                        user_id = row.get('user_id')
                    elif hasattr(row, '__getitem__'):
                        user_id = row[0]
                    else:
                        user_id = getattr(row, 'user_id', None)

                    if user_id:
                        user_list.append({'user_id': user_id})
                return user_list
            return []

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

            if results:
                user_list = []
                for row in results:
                    if isinstance(row, dict):
                        user_id = row.get('user_id')
                    elif hasattr(row, '__getitem__'):
                        user_id = row[0]
                    else:
                        user_id = getattr(row, 'user_id', None)

                    if user_id:
                        user_list.append({'user_id': user_id})
                return user_list
            return []

        except Exception as e:
            logger.error(f"Ошибка получения подписчиков для рассылки: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return []

    # ========== МЕТОДЫ ДЛЯ РАССЫЛОК ==========

    async def create_broadcast(self, title: str, message_text: str, target_users: str = "all",
                              scheduled_time: datetime = None, created_by: int = None,
                              parse_mode: str = None) -> int:
        """Создать рассылку"""
        try:
            # parse_mode игнорируется для совместимости
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO broadcasts
                    (title, message, target_users, scheduled_time, created_by, created_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """
                params = (title, message_text, target_users, scheduled_time, created_by, datetime.now())
            else:  # PostgreSQL
                query = """
                    INSERT INTO broadcasts
                    (title, message, target_users, scheduled_time, created_by, created_at, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'pending')
                    RETURNING id
                """
                params = (title, message_text, target_users, scheduled_time, created_by, datetime.now())

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

    async def get_broadcasts_paginated(self, page: int = 1, per_page: int = 10) -> dict:
        """Получить рассылки с пагинацией"""
        try:
            await self.adapter.connect()

            offset = (page - 1) * per_page

            # Получаем общее количество
            count_result = await self.adapter.fetch_one("SELECT COUNT(*) FROM broadcasts")
            total = self._extract_count(count_result)

            # Получаем рассылки
            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT * FROM broadcasts
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                params = (per_page, offset)
            else:  # PostgreSQL
                query = """
                    SELECT * FROM broadcasts
                    ORDER BY created_at DESC
                    LIMIT $1 OFFSET $2
                """
                params = (per_page, offset)

            results = await self.adapter.fetch_all(query, params)
            broadcasts = []

            if results:
                for row in results:
                    if hasattr(row, '_asdict'):
                        broadcasts.append(row._asdict())
                    elif hasattr(row, 'keys'):
                        broadcasts.append(dict(row))
                    else:
                        # Fallback для tuple
                        broadcasts.append({
                            'id': row[0],
                            'title': row[1],
                            'message': row[2],
                            'status': row[3],
                            'created_at': row[4]
                        })

            await self.adapter.disconnect()

            return {
                'broadcasts': broadcasts,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page if total > 0 else 1,
                'pagination': {
                    'current_page': page,
                    'total_pages': (total + per_page - 1) // per_page if total > 0 else 1,
                    'has_prev': page > 1,
                    'has_next': page * per_page < total,
                    'prev_page': page - 1 if page > 1 else None,
                    'next_page': page + 1 if page * per_page < total else None
                }
            }

        except Exception as e:
            logger.error(f"Ошибка получения рассылок: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return {
                'broadcasts': [],
                'total': 0,
                'page': page,
                'per_page': per_page,
                'pages': 1,
                'pagination': {
                    'current_page': page,
                    'total_pages': 1,
                    'has_prev': False,
                    'has_next': False,
                    'prev_page': None,
                    'next_page': None
                }
            }

    # ========== МЕТОДЫ ДЛЯ АДМИН-ПАНЕЛИ ==========

    async def get_admin_user_by_username(self, username: str) -> Optional[dict]:
        """Получить админ пользователя по username"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = "SELECT * FROM admin_users WHERE username = ? AND is_active = TRUE"
                params = (username,)
            else:  # PostgreSQL
                query = "SELECT * FROM admin_users WHERE username = $1 AND is_active = TRUE"
                params = (username,)

            result = await self.adapter.fetch_one(query, params)
            await self.adapter.disconnect()

            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Ошибка получения админ пользователя {username}: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass
            return None

    async def update_admin_user_login(self, user_id: int):
        """Обновить время последнего входа админ пользователя"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = "UPDATE admin_users SET last_login = ? WHERE id = ?"
                params = (datetime.now(), user_id)
            else:  # PostgreSQL
                query = "UPDATE admin_users SET last_login = $1 WHERE id = $2"
                params = (datetime.now(), user_id)

            await self.adapter.execute(query, params)
            await self.adapter.disconnect()

        except Exception as e:
            logger.error(f"Ошибка обновления входа админ пользователя {user_id}: {e}")
            try:
                await self.adapter.disconnect()
            except:
                pass


    # ========== МЕТОДЫ ПЛАТЕЖЕЙ ==========
    
    async def create_payment(self, user_id: int, amount: int, currency: str = "RUB",
                           payment_id: str = None, invoice_payload: str = None,
                           subscription_months: int = 1) -> str:
        """Создать запись о платеже"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO payments (user_id, payment_id, amount, currency,
                                        invoice_payload, subscription_months)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (user_id, payment_id, amount, currency, invoice_payload, subscription_months)
            else:  # PostgreSQL
                query = """
                    INSERT INTO payments (user_id, payment_id, amount, currency,
                                        invoice_payload, subscription_months)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                """
                params = (user_id, payment_id, amount, currency, invoice_payload, subscription_months)
            
            result = await self.adapter.execute(query, params)
            return str(result) if result else "1"
            
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            raise
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_payment(self, payment_id: str = None, db_id: int = None) -> Optional[dict]:
        """Получить платеж по ID"""
        try:
            await self.adapter.connect()
            
            if payment_id:
                if self.adapter.db_type == 'sqlite':
                    query = "SELECT * FROM payments WHERE payment_id = ?"
                    params = (payment_id,)
                else:  # PostgreSQL
                    query = "SELECT * FROM payments WHERE payment_id = $1"
                    params = (payment_id,)
            elif db_id:
                if self.adapter.db_type == 'sqlite':
                    query = "SELECT * FROM payments WHERE id = ?"
                    params = (db_id,)
                else:  # PostgreSQL
                    query = "SELECT * FROM payments WHERE id = $1"
                    params = (db_id,)
            else:
                return None
            
            result = await self.adapter.fetch_one(query, params)
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"Ошибка получения платежа: {e}")
            return None
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def complete_payment(self, payment_id: str, provider_payment_id: str = None):
        """Завершить платеж и активировать подписку"""
        try:
            await self.adapter.connect()
            
            # Получаем информацию о платеже
            payment = await self.get_payment(payment_id=payment_id)
            if not payment:
                logger.error(f"Платеж {payment_id} не найден")
                return False
            
            # Обновляем статус платежа
            if self.adapter.db_type == 'sqlite':
                query = """
                    UPDATE payments 
                    SET status = 'completed', provider_payment_id = ?, completed_at = ?
                    WHERE payment_id = ?
                """
                params = (provider_payment_id, datetime.now(), payment_id)
            else:  # PostgreSQL
                query = """
                    UPDATE payments 
                    SET status = 'completed', provider_payment_id = $1, completed_at = $2
                    WHERE payment_id = $3
                """
                params = (provider_payment_id, datetime.now(), payment_id)
            
            await self.adapter.execute(query, params)
            
            # Активируем подписку пользователю
            end_date = datetime.now() + timedelta(days=30 * payment['subscription_months'])
            
            if self.adapter.db_type == 'sqlite':
                sub_query = """
                    UPDATE users
                    SET is_subscribed = TRUE, subscription_end = ?,
                        last_payment_date = ?, payment_provider = 'yookassa'
                    WHERE user_id = ?
                """
                sub_params = (end_date, datetime.now(), payment['user_id'])
            else:  # PostgreSQL
                sub_query = """
                    UPDATE users
                    SET is_subscribed = TRUE, subscription_end = $1,
                        last_payment_date = $2, payment_provider = 'yookassa'
                    WHERE user_id = $3
                """
                sub_params = (end_date, datetime.now(), payment['user_id'])
            
            await self.adapter.execute(sub_query, sub_params)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка завершения платежа: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_user_payments(self, user_id: int) -> List[dict]:
        """Получить все платежи пользователя"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT * FROM payments
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                """
                params = (user_id,)
            else:  # PostgreSQL
                query = """
                    SELECT * FROM payments
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                """
                params = (user_id,)
            
            results = await self.adapter.fetch_all(query, params)
            return [dict(row) for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения платежей пользователя: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def update_payment_status(self, payment_id: str, status: str):
        """Обновить статус платежа"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = "UPDATE payments SET status = ? WHERE payment_id = ?"
                params = (status, payment_id)
            else:  # PostgreSQL
                query = "UPDATE payments SET status = $1 WHERE payment_id = $2"
                params = (status, payment_id)
            
            await self.adapter.execute(query, params)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса платежа: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass


    # ========== МЕТОДЫ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ ==========
    
    async def get_users_paginated(self, page: int = 1, per_page: int = 10, search: str = None, filter_type: str = None) -> dict:
        """Получить пользователей с пагинацией"""
        try:
            await self.adapter.connect()
            
            offset = (page - 1) * per_page
            where_conditions = []
            params = []
            
            if search:
                where_conditions.append("(username LIKE ? OR first_name LIKE ? OR last_name LIKE ?)")
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])
            
            if filter_type == 'subscribed':
                where_conditions.append("is_subscribed = TRUE")
            elif filter_type == 'blocked':
                where_conditions.append("blocked = TRUE")
            
            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Получаем общее количество
            if self.adapter.db_type == 'sqlite':
                count_query = f"SELECT COUNT(*) FROM users{where_clause}"
                query = f"""
                    SELECT * FROM users{where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                query_params = params + [per_page, offset]
            else:  # PostgreSQL
                # Конвертируем параметры для PostgreSQL
                pg_where_clause = where_clause
                for i, _ in enumerate(params):
                    pg_where_clause = pg_where_clause.replace('?', f'${i+1}', 1)
                
                count_query = f"SELECT COUNT(*) FROM users{pg_where_clause}"
                query = f"""
                    SELECT * FROM users{pg_where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${len(params)+1} OFFSET ${len(params)+2}
                """
                query_params = params + [per_page, offset]
            
            count_result = await self.adapter.fetch_one(count_query, params)
            total = self._extract_count(count_result)
            
            results = await self.adapter.fetch_all(query, query_params)
            users = [dict(row) for row in results] if results else []
            
            return {
                'users': users,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page if total > 0 else 1
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователей: {e}")
            return {'users': [], 'total': 0, 'page': page, 'per_page': per_page, 'pages': 1}
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_all_users(self, limit: int = None) -> List[dict]:
        """Получить всех пользователей"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = "SELECT * FROM users ORDER BY created_at DESC"
                if limit:
                    query += f" LIMIT {limit}"
                params = ()
            else:  # PostgreSQL
                query = "SELECT * FROM users ORDER BY created_at DESC"
                if limit:
                    query += f" LIMIT ${1}"
                    params = (limit,)
                else:
                    params = ()
            
            results = await self.adapter.fetch_all(query, params)
            return [dict(row) for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения всех пользователей: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_active_users(self, limit: int = None) -> List[dict]:
        """Получить активных пользователей"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT * FROM users 
                    WHERE blocked = FALSE AND bot_blocked = FALSE
                    ORDER BY last_request DESC
                """
                if limit:
                    query += f" LIMIT {limit}"
                params = ()
            else:  # PostgreSQL
                query = """
                    SELECT * FROM users 
                    WHERE blocked = FALSE AND bot_blocked = FALSE
                    ORDER BY last_request DESC
                """
                if limit:
                    query += f" LIMIT ${1}"
                    params = (limit,)
                else:
                    params = ()
            
            results = await self.adapter.fetch_all(query, params)
            return [dict(row) for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения активных пользователей: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_subscribers(self, limit: int = None) -> List[dict]:
        """Получить подписчиков"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT * FROM users 
                    WHERE is_subscribed = TRUE AND subscription_end > ?
                    ORDER BY subscription_end DESC
                """
                params = (datetime.now(),)
                if limit:
                    query += f" LIMIT {limit}"
            else:  # PostgreSQL
                query = """
                    SELECT * FROM users 
                    WHERE is_subscribed = TRUE AND subscription_end > $1
                    ORDER BY subscription_end DESC
                """
                params = (datetime.now(),)
                if limit:
                    query += f" LIMIT ${2}"
                    params = params + (limit,)
            
            results = await self.adapter.fetch_all(query, params)
            return [dict(row) for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения подписчиков: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def delete_user(self, user_id: int) -> bool:
        """Удалить пользователя"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = "DELETE FROM users WHERE user_id = ?"
                params = (user_id,)
            else:  # PostgreSQL
                query = "DELETE FROM users WHERE user_id = $1"
                params = (user_id,)
            
            await self.adapter.execute(query, params)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления пользователя: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def bulk_delete_users(self, user_ids: List[int]) -> bool:
        """Массовое удаление пользователей"""
        try:
            await self.adapter.connect()
            
            if not user_ids:
                return True
            
            placeholders = ','.join(['?' if self.adapter.db_type == 'sqlite' else f'${i+1}' for i in range(len(user_ids))])
            query = f"DELETE FROM users WHERE user_id IN ({placeholders})"
            
            await self.adapter.execute(query, user_ids)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка массового удаления пользователей: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def update_user_permissions(self, user_id: int, unlimited_access: bool = None, 
                                    blocked: bool = None, notes: str = None, blocked_by: int = None) -> bool:
        """Обновить права пользователя"""
        try:
            await self.adapter.connect()
            
            updates = []
            params = []
            
            if unlimited_access is not None:
                updates.append("unlimited_access = ?")
                params.append(unlimited_access)
            
            if blocked is not None:
                updates.append("blocked = ?")
                params.append(blocked)
                if blocked:
                    updates.append("blocked_at = ?")
                    params.append(datetime.now())
                    if blocked_by:
                        updates.append("blocked_by = ?")
                        params.append(blocked_by)
            
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)
            
            if not updates:
                return True
            
            if self.adapter.db_type == 'sqlite':
                query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
                params.append(user_id)
            else:  # PostgreSQL
                pg_updates = []
                for i, update in enumerate(updates):
                    pg_updates.append(update.replace('?', f'${i+1}'))
                query = f"UPDATE users SET {', '.join(pg_updates)} WHERE user_id = ${len(params)+1}"
                params.append(user_id)
            
            await self.adapter.execute(query, params)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления прав пользователя: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def update_user_role(self, user_id: int, role: str) -> bool:
        """Обновить роль пользователя"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = "UPDATE users SET role = ? WHERE user_id = ?"
                params = (role, user_id)
            else:  # PostgreSQL
                query = "UPDATE users SET role = $1 WHERE user_id = $2"
                params = (role, user_id)
            
            await self.adapter.execute(query, params)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления роли пользователя: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_users_by_role(self, role: str) -> List[dict]:
        """Получить пользователей по роли"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = "SELECT * FROM users WHERE role = ? ORDER BY created_at DESC"
                params = (role,)
            else:  # PostgreSQL
                query = "SELECT * FROM users WHERE role = $1 ORDER BY created_at DESC"
                params = (role,)
            
            results = await self.adapter.fetch_all(query, params)
            return [dict(row) for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователей по роли: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    # ========== АДМИН-ФУНКЦИИ ==========

    async def create_admin_user(self, username: str, email: str, password_hash: str,
                              role: str = 'moderator', created_by: int = None) -> bool:
        """Создать админ пользователя"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO admin_users (username, email, password_hash, role, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (username, email, password_hash, role, created_by, datetime.now())
            else:  # PostgreSQL
                query = """
                    INSERT INTO admin_users (username, email, password_hash, role, created_by, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """
                params = (username, email, password_hash, role, created_by, datetime.now())

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка создания админ пользователя: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_admin_users(self) -> List[dict]:
        """Получить всех админ пользователей"""
        try:
            await self.adapter.connect()

            query = "SELECT * FROM admin_users WHERE is_active = TRUE ORDER BY created_at DESC"
            results = await self.adapter.fetch_all(query, ())

            admin_users = []
            if results:
                for row in results:
                    if hasattr(row, '_asdict'):
                        admin_users.append(row._asdict())
                    elif hasattr(row, 'keys'):
                        admin_users.append(dict(row))
                    else:
                        admin_users.append({
                            'id': row[0],
                            'username': row[1],
                            'email': row[2],
                            'role': row[4],
                            'created_at': row[6]
                        })

            return admin_users

        except Exception as e:
            logger.error(f"Ошибка получения админ пользователей: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def log_admin_action(self, admin_user_id: int, action: str, resource_type: str = None,
                             resource_id: int = None, details: str = None,
                             ip_address: str = None, user_agent: str = None) -> bool:
        """Логировать действие админа"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO audit_logs (admin_user_id, action, resource_type, resource_id,
                                          details, ip_address, user_agent, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (admin_user_id, action, resource_type, resource_id,
                         details, ip_address, user_agent, datetime.now())
            else:  # PostgreSQL
                query = """
                    INSERT INTO audit_logs (admin_user_id, action, resource_type, resource_id,
                                          details, ip_address, user_agent, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """
                params = (admin_user_id, action, resource_type, resource_id,
                         details, ip_address, user_agent, datetime.now())

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка логирования действия админа: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_audit_logs(self, page: int = 1, per_page: int = 50,
                           admin_user_id: int = None, action: str = None) -> dict:
        """Получить логи аудита"""
        try:
            await self.adapter.connect()

            offset = (page - 1) * per_page
            where_conditions = []
            params = []

            if admin_user_id:
                where_conditions.append("admin_user_id = ?")
                params.append(admin_user_id)

            if action:
                where_conditions.append("action = ?")
                params.append(action)

            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""

            # Получаем общее количество
            if self.adapter.db_type == 'sqlite':
                count_query = f"SELECT COUNT(*) FROM audit_logs{where_clause}"
                query = f"""
                    SELECT * FROM audit_logs{where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                query_params = params + [per_page, offset]
            else:  # PostgreSQL
                pg_where_clause = where_clause
                for i, _ in enumerate(params):
                    pg_where_clause = pg_where_clause.replace('?', f'${i+1}', 1)

                count_query = f"SELECT COUNT(*) FROM audit_logs{pg_where_clause}"
                query = f"""
                    SELECT * FROM audit_logs{pg_where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${len(params)+1} OFFSET ${len(params)+2}
                """
                query_params = params + [per_page, offset]

            count_result = await self.adapter.fetch_one(count_query, params)
            total = self._extract_count(count_result)

            results = await self.adapter.fetch_all(query, query_params)
            logs = []

            if results:
                for row in results:
                    if hasattr(row, '_asdict'):
                        logs.append(row._asdict())
                    elif hasattr(row, 'keys'):
                        logs.append(dict(row))
                    else:
                        logs.append({
                            'id': row[0],
                            'admin_user_id': row[1],
                            'action': row[2],
                            'resource_type': row[3],
                            'created_at': row[8]
                        })

            return {
                'logs': logs,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page if total > 0 else 1
            }

        except Exception as e:
            logger.error(f"Ошибка получения логов аудита: {e}")
            return {'logs': [], 'total': 0, 'page': page, 'per_page': per_page, 'pages': 1}
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_user_activity_chart_data(self, days: int = 30) -> List[dict]:
        """Получить данные для графика активности пользователей"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM users
                    WHERE created_at >= date('now', '-{} days')
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """.format(days)
                params = ()
            else:  # PostgreSQL
                query = """
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM users
                    WHERE created_at >= NOW() - INTERVAL '%s days'
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """
                params = (days,)

            results = await self.adapter.fetch_all(query, params)
            chart_data = []

            if results:
                for row in results:
                    if hasattr(row, '_asdict'):
                        chart_data.append(row._asdict())
                    elif hasattr(row, 'keys'):
                        chart_data.append(dict(row))
                    else:
                        chart_data.append({
                            'date': row[0],
                            'count': row[1]
                        })

            return chart_data

        except Exception as e:
            logger.error(f"Ошибка получения данных активности: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_blocked_users_count(self) -> int:
        """Получить количество заблокированных пользователей"""
        try:
            await self.adapter.connect()

            query = "SELECT COUNT(*) FROM users WHERE blocked = TRUE"
            result = await self.adapter.fetch_one(query, ())
            return self._extract_count(result)

        except Exception as e:
            logger.error(f"Ошибка получения количества заблокированных: {e}")
            return 0
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def _run_migrations(self) -> bool:
        """Запустить миграции"""
        try:
            # Этот метод может быть реализован позже
            # Пока возвращаем True для совместимости
            logger.info("Миграции выполнены (заглушка)")
            return True

        except Exception as e:
            logger.error(f"Ошибка выполнения миграций: {e}")
            return False

    # ========== МЕТОДЫ РАССЫЛОК И УВЕДОМЛЕНИЙ ==========

    async def get_broadcast_by_id(self, broadcast_id: int) -> Optional[dict]:
        """Получить рассылку по ID"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = "SELECT * FROM broadcasts WHERE id = ?"
                params = (broadcast_id,)
            else:  # PostgreSQL
                query = "SELECT * FROM broadcasts WHERE id = $1"
                params = (broadcast_id,)

            result = await self.adapter.fetch_one(query, params)

            if result:
                if hasattr(result, '_asdict'):
                    return result._asdict()
                elif hasattr(result, 'keys'):
                    return dict(result)
                else:
                    return {
                        'id': result[0],
                        'title': result[1],
                        'message': result[2],
                        'status': result[3],
                        'created_at': result[4]
                    }

            return None

        except Exception as e:
            logger.error(f"Ошибка получения рассылки: {e}")
            return None
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_broadcasts_list(self) -> List[dict]:
        """Получить список всех рассылок"""
        try:
            await self.adapter.connect()

            query = "SELECT * FROM broadcasts ORDER BY created_at DESC"
            results = await self.adapter.fetch_all(query, ())

            broadcasts = []
            if results:
                for row in results:
                    if hasattr(row, '_asdict'):
                        broadcasts.append(row._asdict())
                    elif hasattr(row, 'keys'):
                        broadcasts.append(dict(row))
                    else:
                        broadcasts.append({
                            'id': row[0],
                            'title': row[1],
                            'message': row[2],
                            'status': row[3],
                            'created_at': row[4]
                        })

            return broadcasts

        except Exception as e:
            logger.error(f"Ошибка получения списка рассылок: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_broadcasts_stats(self) -> dict:
        """Получить статистику рассылок"""
        try:
            await self.adapter.connect()

            # Общее количество рассылок
            total_query = "SELECT COUNT(*) FROM broadcasts"
            total_result = await self.adapter.fetch_one(total_query, ())
            total = self._extract_count(total_result)

            # Количество по статусам
            status_query = "SELECT status, COUNT(*) FROM broadcasts GROUP BY status"
            status_results = await self.adapter.fetch_all(status_query, ())

            stats = {
                'total': total,
                'completed': 0,
                'pending': 0,
                'failed': 0,
                'in_progress': 0
            }

            if status_results:
                for row in status_results:
                    if isinstance(row, dict):
                        status = row.get('status')
                        count = row.get('count', 0)
                    elif hasattr(row, '__getitem__'):
                        status = row[0]
                        count = self._extract_count({'count': row[1]}) if isinstance(row[1], (int, str)) else row[1]
                    else:
                        status = getattr(row, 'status', None)
                        count = getattr(row, 'count', 0)

                    if status and status in stats:
                        stats[status] = int(count)

            return stats

        except Exception as e:
            logger.error(f"Ошибка получения статистики рассылок: {e}")
            return {'total': 0, 'completed': 0, 'pending': 0, 'failed': 0, 'in_progress': 0}
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_broadcast_detailed_stats(self, broadcast_id: int) -> dict:
        """Получить детальную статистику рассылки"""
        try:
            await self.adapter.connect()

            # Основная информация о рассылке
            broadcast = await self.get_broadcast_by_id(broadcast_id)
            if not broadcast:
                return {}

            # Статистика доставки
            if self.adapter.db_type == 'sqlite':
                stats_query = """
                    SELECT status, COUNT(*) as count
                    FROM broadcast_logs
                    WHERE broadcast_id = ?
                    GROUP BY status
                """
                params = (broadcast_id,)
            else:  # PostgreSQL
                stats_query = """
                    SELECT status, COUNT(*) as count
                    FROM broadcast_logs
                    WHERE broadcast_id = $1
                    GROUP BY status
                """
                params = (broadcast_id,)

            stats_results = await self.adapter.fetch_all(stats_query, params)

            delivery_stats = {
                'sent': 0,
                'delivered': 0,
                'failed': 0,
                'blocked': 0
            }

            if stats_results:
                for row in stats_results:
                    status = row[0] if hasattr(row, '__getitem__') else row.status
                    count = row[1] if hasattr(row, '__getitem__') else row.count
                    if status in delivery_stats:
                        delivery_stats[status] = count

            return {
                'broadcast': broadcast,
                'delivery_stats': delivery_stats
            }

        except Exception as e:
            logger.error(f"Ошибка получения детальной статистики рассылки: {e}")
            return {}
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_broadcast_logs(self, broadcast_id: int, page: int = 1, per_page: int = 50, status: str = None) -> dict:
        """Получить логи рассылки"""
        try:
            await self.adapter.connect()

            offset = (page - 1) * per_page
            where_conditions = [f"broadcast_id = {'?' if self.adapter.db_type == 'sqlite' else '$1'}"]
            params = [broadcast_id]

            if status:
                where_conditions.append(f"status = {'?' if self.adapter.db_type == 'sqlite' else f'${len(params)+1}'}")
                params.append(status)

            where_clause = " WHERE " + " AND ".join(where_conditions)

            # Получаем общее количество
            if self.adapter.db_type == 'sqlite':
                count_query = f"SELECT COUNT(*) FROM broadcast_logs{where_clause}"
                query = f"""
                    SELECT * FROM broadcast_logs{where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                query_params = params + [per_page, offset]
            else:  # PostgreSQL
                count_query = f"SELECT COUNT(*) FROM broadcast_logs{where_clause}"
                query = f"""
                    SELECT * FROM broadcast_logs{where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${len(params)+1} OFFSET ${len(params)+2}
                """
                query_params = params + [per_page, offset]

            count_result = await self.adapter.fetch_one(count_query, params)
            total = self._extract_count(count_result)

            results = await self.adapter.fetch_all(query, query_params)
            logs = []

            if results:
                for row in results:
                    if hasattr(row, '_asdict'):
                        logs.append(row._asdict())
                    elif hasattr(row, 'keys'):
                        logs.append(dict(row))
                    else:
                        logs.append({
                            'id': row[0],
                            'broadcast_id': row[1],
                            'user_id': row[2],
                            'status': row[3],
                            'created_at': row[6]
                        })

            return {
                'logs': logs,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page if total > 0 else 1
            }

        except Exception as e:
            logger.error(f"Ошибка получения логов рассылки: {e}")
            return {'logs': [], 'total': 0, 'page': page, 'per_page': per_page, 'pages': 1}
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_all_broadcast_logs(self, broadcast_id: int) -> List[dict]:
        """Получить все логи рассылки"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = "SELECT * FROM broadcast_logs WHERE broadcast_id = ? ORDER BY created_at DESC"
                params = (broadcast_id,)
            else:  # PostgreSQL
                query = "SELECT * FROM broadcast_logs WHERE broadcast_id = $1 ORDER BY created_at DESC"
                params = (broadcast_id,)

            results = await self.adapter.fetch_all(query, params)
            logs = []

            if results:
                for row in results:
                    if hasattr(row, '_asdict'):
                        logs.append(row._asdict())
                    elif hasattr(row, 'keys'):
                        logs.append(dict(row))
                    else:
                        logs.append({
                            'id': row[0],
                            'broadcast_id': row[1],
                            'user_id': row[2],
                            'status': row[3],
                            'created_at': row[6]
                        })

            return logs

        except Exception as e:
            logger.error(f"Ошибка получения всех логов рассылки: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def log_broadcast_delivery(self, broadcast_id: int, user_id: int, status: str,
                                   message: str = None, error_details: str = None) -> bool:
        """Логировать доставку рассылки"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO broadcast_logs (broadcast_id, user_id, status, message, error_details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (broadcast_id, user_id, status, message, error_details, datetime.now())
            else:  # PostgreSQL
                query = """
                    INSERT INTO broadcast_logs (broadcast_id, user_id, status, message, error_details, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """
                params = (broadcast_id, user_id, status, message, error_details, datetime.now())

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка логирования доставки рассылки: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def update_broadcast_status(self, broadcast_id: int, status: str) -> bool:
        """Обновить статус рассылки"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = "UPDATE broadcasts SET status = ? WHERE id = ?"
                params = (status, broadcast_id)
            else:  # PostgreSQL
                query = "UPDATE broadcasts SET status = $1 WHERE id = $2"
                params = (status, broadcast_id)

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка обновления статуса рассылки: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def update_broadcast_stats(self, broadcast_id: int, sent_count: int = None,
                                   failed_count: int = None, completed: bool = None,
                                   started_at: datetime = None, error_message: str = None) -> bool:
        """Обновить статистику рассылки"""
        try:
            await self.adapter.connect()

            updates = []
            params = []

            if sent_count is not None:
                updates.append("sent_count = ?")
                params.append(sent_count)

            if failed_count is not None:
                updates.append("failed_count = ?")
                params.append(failed_count)

            if completed is not None:
                updates.append("completed = ?")
                params.append(completed)
                if completed:
                    updates.append("completed_at = ?")
                    params.append(datetime.now())

            if started_at is not None:
                updates.append("started_at = ?")
                params.append(started_at)

            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)

            if not updates:
                return True

            if self.adapter.db_type == 'sqlite':
                query = f"UPDATE broadcasts SET {', '.join(updates)} WHERE id = ?"
                params.append(broadcast_id)
            else:  # PostgreSQL
                pg_updates = []
                for i, update in enumerate(updates):
                    pg_updates.append(update.replace('?', f'${i+1}'))
                query = f"UPDATE broadcasts SET {', '.join(pg_updates)} WHERE id = ${len(params)+1}"
                params.append(broadcast_id)

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка обновления статистики рассылки: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_broadcast_target_users(self, broadcast_id: int) -> List[dict]:
        """Получить целевых пользователей рассылки"""
        try:
            await self.adapter.connect()

            # Получаем информацию о рассылке
            broadcast = await self.get_broadcast_by_id(broadcast_id)
            if not broadcast:
                return []

            # Определяем целевую аудиторию на основе типа рассылки
            target_type = broadcast.get('target_type', 'all')

            if target_type == 'subscribers':
                query = """
                    SELECT * FROM users
                    WHERE is_subscribed = TRUE AND subscription_end > ?
                    AND blocked = FALSE AND bot_blocked = FALSE
                """
                params = (datetime.now(),)
            elif target_type == 'active':
                query = """
                    SELECT * FROM users
                    WHERE blocked = FALSE AND bot_blocked = FALSE
                    AND last_request > ?
                """
                params = (datetime.now() - timedelta(days=30),)
            else:  # all
                query = """
                    SELECT * FROM users
                    WHERE blocked = FALSE AND bot_blocked = FALSE
                """
                params = ()

            if self.adapter.db_type == 'postgresql':
                # Конвертируем параметры для PostgreSQL
                if params:
                    pg_query = query.replace('?', '$1')
                    if len(params) > 1:
                        for i in range(1, len(params)):
                            pg_query = pg_query.replace('?', f'${i+1}', 1)
                    query = pg_query

            results = await self.adapter.fetch_all(query, params)
            users = []

            if results:
                for row in results:
                    if hasattr(row, '_asdict'):
                        users.append(row._asdict())
                    elif hasattr(row, 'keys'):
                        users.append(dict(row))
                    else:
                        users.append({
                            'user_id': row[0],
                            'username': row[1],
                            'first_name': row[2],
                            'last_name': row[3]
                        })

            return users

        except Exception as e:
            logger.error(f"Ошибка получения целевых пользователей: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_target_audience_count(self, target_type: str) -> int:
        """Получить количество пользователей в целевой аудитории"""
        try:
            await self.adapter.connect()

            if target_type == 'subscribers':
                query = """
                    SELECT COUNT(*) FROM users
                    WHERE is_subscribed = TRUE AND subscription_end > ?
                    AND blocked = FALSE AND bot_blocked = FALSE
                """
                params = (datetime.now(),)
            elif target_type == 'active':
                query = """
                    SELECT COUNT(*) FROM users
                    WHERE blocked = FALSE AND bot_blocked = FALSE
                    AND last_request > ?
                """
                params = (datetime.now() - timedelta(days=30),)
            else:  # all
                query = """
                    SELECT COUNT(*) FROM users
                    WHERE blocked = FALSE AND bot_blocked = FALSE
                """
                params = ()

            if self.adapter.db_type == 'postgresql' and params:
                query = query.replace('?', '$1')
                if len(params) > 1:
                    for i in range(1, len(params)):
                        query = query.replace('?', f'${i+1}', 1)

            result = await self.adapter.fetch_one(query, params)
            return self._extract_count(result)

        except Exception as e:
            logger.error(f"Ошибка получения количества целевой аудитории: {e}")
            return 0
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    # ========== МЕТОДЫ ШАБЛОНОВ СООБЩЕНИЙ ==========

    async def create_message_template(self, name: str, content: str, parse_mode: str = 'HTML',
                                    category: str = 'general', created_by: int = None) -> bool:
        """Создать шаблон сообщения"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO message_templates (name, content, parse_mode, category, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (name, content, parse_mode, category, created_by, datetime.now())
            else:  # PostgreSQL
                query = """
                    INSERT INTO message_templates (name, content, parse_mode, category, created_by, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """
                params = (name, content, parse_mode, category, created_by, datetime.now())

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка создания шаблона сообщения: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_message_templates(self, category: str = None, is_active: bool = True) -> List[dict]:
        """Получить шаблоны сообщений"""
        try:
            await self.adapter.connect()

            where_conditions = []
            params = []

            if is_active is not None:
                where_conditions.append("is_active = ?")
                params.append(is_active)

            if category:
                where_conditions.append("category = ?")
                params.append(category)

            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""

            if self.adapter.db_type == 'sqlite':
                query = f"SELECT * FROM message_templates{where_clause} ORDER BY created_at DESC"
            else:  # PostgreSQL
                pg_where_clause = where_clause
                for i, _ in enumerate(params):
                    pg_where_clause = pg_where_clause.replace('?', f'${i+1}', 1)
                query = f"SELECT * FROM message_templates{pg_where_clause} ORDER BY created_at DESC"

            results = await self.adapter.fetch_all(query, params)
            templates = []

            if results:
                for row in results:
                    if hasattr(row, '_asdict'):
                        templates.append(row._asdict())
                    elif hasattr(row, 'keys'):
                        templates.append(dict(row))
                    else:
                        templates.append({
                            'id': row[0],
                            'name': row[1],
                            'content': row[2],
                            'parse_mode': row[3],
                            'category': row[4],
                            'created_at': row[8]
                        })

            return templates

        except Exception as e:
            logger.error(f"Ошибка получения шаблонов сообщений: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_message_template(self, template_id: int) -> Optional[dict]:
        """Получить шаблон сообщения по ID"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = "SELECT * FROM message_templates WHERE id = ?"
                params = (template_id,)
            else:  # PostgreSQL
                query = "SELECT * FROM message_templates WHERE id = $1"
                params = (template_id,)

            result = await self.adapter.fetch_one(query, params)

            if result:
                if hasattr(result, '_asdict'):
                    return result._asdict()
                elif hasattr(result, 'keys'):
                    return dict(result)
                else:
                    return {
                        'id': result[0],
                        'name': result[1],
                        'content': result[2],
                        'parse_mode': result[3],
                        'category': result[4],
                        'created_at': result[8]
                    }

            return None

        except Exception as e:
            logger.error(f"Ошибка получения шаблона сообщения: {e}")
            return None
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def update_message_template(self, template_id: int, name: str = None, content: str = None,
                                    parse_mode: str = None, category: str = None, is_active: bool = None) -> bool:
        """Обновить шаблон сообщения"""
        try:
            await self.adapter.connect()

            updates = []
            params = []

            if name is not None:
                updates.append("name = ?")
                params.append(name)

            if content is not None:
                updates.append("content = ?")
                params.append(content)

            if parse_mode is not None:
                updates.append("parse_mode = ?")
                params.append(parse_mode)

            if category is not None:
                updates.append("category = ?")
                params.append(category)

            if is_active is not None:
                updates.append("is_active = ?")
                params.append(is_active)

            if not updates:
                return True

            updates.append("updated_at = ?")
            params.append(datetime.now())

            if self.adapter.db_type == 'sqlite':
                query = f"UPDATE message_templates SET {', '.join(updates)} WHERE id = ?"
                params.append(template_id)
            else:  # PostgreSQL
                pg_updates = []
                for i, update in enumerate(updates):
                    pg_updates.append(update.replace('?', f'${i+1}'))
                query = f"UPDATE message_templates SET {', '.join(pg_updates)} WHERE id = ${len(params)+1}"
                params.append(template_id)

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка обновления шаблона сообщения: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    # ========== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ==========

    async def get_detailed_stats(self) -> dict:
        """Получить детальную статистику системы"""
        try:
            await self.adapter.connect()

            # Статистика пользователей
            users_total_query = "SELECT COUNT(*) FROM users"
            users_total_result = await self.adapter.fetch_one(users_total_query, ())
            users_total = self._extract_count(users_total_result)

            users_active_query = "SELECT COUNT(*) FROM users WHERE blocked = FALSE AND bot_blocked = FALSE"
            users_active_result = await self.adapter.fetch_one(users_active_query, ())
            users_active = self._extract_count(users_active_result)

            users_subscribed_query = "SELECT COUNT(*) FROM users WHERE is_subscribed = TRUE AND subscription_end > ?"
            users_subscribed_result = await self.adapter.fetch_one(users_subscribed_query, (datetime.now(),))
            users_subscribed = self._extract_count(users_subscribed_result)

            # Статистика запросов
            requests_total_query = "SELECT COUNT(*) FROM requests"
            requests_total_result = await self.adapter.fetch_one(requests_total_query, ())
            requests_total = self._extract_count(requests_total_result)

            # Статистика платежей
            payments_total_query = "SELECT COUNT(*) FROM payments"
            payments_total_result = await self.adapter.fetch_one(payments_total_query, ())
            payments_total = self._extract_count(payments_total_result)

            payments_completed_query = "SELECT COUNT(*) FROM payments WHERE status = 'completed'"
            payments_completed_result = await self.adapter.fetch_one(payments_completed_query, ())
            payments_completed = self._extract_count(payments_completed_result)

            # Статистика рассылок
            broadcasts_total_query = "SELECT COUNT(*) FROM broadcasts"
            broadcasts_total_result = await self.adapter.fetch_one(broadcasts_total_query, ())
            broadcasts_total = self._extract_count(broadcasts_total_result)

            return {
                'users': {
                    'total': users_total,
                    'active': users_active,
                    'subscribed': users_subscribed,
                    'blocked': users_total - users_active
                },
                'requests': {
                    'total': requests_total
                },
                'payments': {
                    'total': payments_total,
                    'completed': payments_completed,
                    'pending': payments_total - payments_completed
                },
                'broadcasts': {
                    'total': broadcasts_total
                }
            }

        except Exception as e:
            logger.error(f"Ошибка получения детальной статистики: {e}")
            return {
                'users': {'total': 0, 'active': 0, 'subscribed': 0, 'blocked': 0},
                'requests': {'total': 0},
                'payments': {'total': 0, 'completed': 0, 'pending': 0},
                'broadcasts': {'total': 0}
            }
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def mark_user_bot_blocked(self, user_id: int) -> bool:
        """Отметить пользователя как заблокированного ботом"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = "UPDATE users SET bot_blocked = TRUE WHERE user_id = ?"
                params = (user_id,)
            else:  # PostgreSQL
                query = "UPDATE users SET bot_blocked = TRUE WHERE user_id = $1"
                params = (user_id,)

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка отметки пользователя как заблокированного: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def update_user_bot_blocked_status(self, user_id: int, blocked: bool) -> bool:
        """Обновить статус блокировки пользователя ботом"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = "UPDATE users SET bot_blocked = ? WHERE user_id = ?"
                params = (blocked, user_id)
            else:  # PostgreSQL
                query = "UPDATE users SET bot_blocked = $1 WHERE user_id = $2"
                params = (blocked, user_id)

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка обновления статуса блокировки: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def reset_user_requests(self, user_id: int) -> bool:
        """Сбросить счетчик запросов пользователя"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = "UPDATE users SET requests_used = 0 WHERE user_id = ?"
                params = (user_id,)
            else:  # PostgreSQL
                query = "UPDATE users SET requests_used = 0 WHERE user_id = $1"
                params = (user_id,)

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка сброса счетчика запросов: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def update_subscription(self, user_id: int, is_subscribed: bool, subscription_end: datetime = None) -> bool:
        """Обновить подписку пользователя"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = "UPDATE users SET is_subscribed = ?, subscription_end = ? WHERE user_id = ?"
                params = (is_subscribed, subscription_end, user_id)
            else:  # PostgreSQL
                query = "UPDATE users SET is_subscribed = $1, subscription_end = $2 WHERE user_id = $3"
                params = (is_subscribed, subscription_end, user_id)

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка обновления подписки: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass
