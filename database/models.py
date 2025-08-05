"""
Модели базы данных с production-ready функциональностью
"""
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)

# Импортируем production-ready компоненты
try:
    from .production_manager import ProductionDatabaseManager
    from .monitoring import QueryTimer, monitor_query
    PRODUCTION_FEATURES_AVAILABLE = True
except ImportError:
    PRODUCTION_FEATURES_AVAILABLE = False
    logger.warning("Production-ready функции базы данных недоступны")


class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path

        # Инициализируем production-ready менеджер если доступен
        if PRODUCTION_FEATURES_AVAILABLE:
            self.production_manager = ProductionDatabaseManager(db_path)
        else:
            self.production_manager = None

    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, существуют ли основные таблицы
            cursor = await db.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('users', 'requests', 'broadcasts', 'payments')
            """)
            existing_tables = {row[0] for row in await cursor.fetchall()}

            # Создаем только отсутствующие таблицы
            if 'users' not in existing_tables:
                await db.execute("""
                    CREATE TABLE users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        requests_used INTEGER DEFAULT 0,
                        is_subscribed BOOLEAN DEFAULT FALSE,
                        subscription_end TIMESTAMP,
                        last_request TIMESTAMP,
                        payment_provider TEXT DEFAULT 'yookassa',
                        last_payment_date TIMESTAMP,
                        role TEXT DEFAULT 'user',
                        blocked BOOLEAN DEFAULT FALSE,
                        bot_blocked BOOLEAN DEFAULT FALSE
                    )
                """)

            if 'requests' not in existing_tables:
                await db.execute("""
                    CREATE TABLE requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        channels_input TEXT,
                        results TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """)

            if 'broadcasts' not in existing_tables:
                await db.execute("""
                    CREATE TABLE broadcasts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_text TEXT,
                        sent_count INTEGER DEFAULT 0,
                        failed_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed BOOLEAN DEFAULT FALSE
                    )
                """)

            if 'payments' not in existing_tables:
                await db.execute("""
                    CREATE TABLE payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        payment_id TEXT UNIQUE,
                        amount INTEGER NOT NULL,
                        currency TEXT DEFAULT 'RUB',
                        status TEXT DEFAULT 'pending',
                        provider TEXT DEFAULT 'yookassa',
                        provider_payment_id TEXT,
                        invoice_payload TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        subscription_months INTEGER DEFAULT 1,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """)

            await db.commit()

        # Запускаем миграции для обновления существующих таблиц
        await self._run_migrations()

        # Запускаем миграции для админ-панели только если нужно
        try:
            from .admin_migrations import run_admin_migrations
            await run_admin_migrations(self.db_path)
        except Exception as e:
            logger.error(f"Ошибка выполнения миграций админ-панели: {e}")

    async def _run_migrations(self):
        """Выполнить миграции для обновления существующих таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, какие колонки существуют в таблице users
            cursor = await db.execute("PRAGMA table_info(users)")
            existing_columns = {row[1] for row in await cursor.fetchall()}

            # Список новых колонок для добавления
            new_columns = {
                'payment_provider': 'TEXT DEFAULT "yookassa"',
                'last_payment_date': 'TIMESTAMP',
                'role': 'TEXT DEFAULT "user"',
                'blocked': 'BOOLEAN DEFAULT FALSE',
                'bot_blocked': 'BOOLEAN DEFAULT FALSE'
            }

            # Добавляем отсутствующие колонки
            for column_name, column_def in new_columns.items():
                if column_name not in existing_columns:
                    try:
                        await db.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
                        logger.info(f"Добавлена колонка {column_name} в таблицу users")
                    except Exception as e:
                        logger.error(f"Ошибка при добавлении колонки {column_name}: {e}")

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
                         first_name: str = None, last_name: str = None, role: str = None):
        """Создать пользователя"""
        from bot.utils.roles import TelegramUserPermissions

        # Определяем роль пользователя
        if role is None:
            role = TelegramUserPermissions.get_user_role(user_id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users
                (user_id, username, first_name, last_name, created_at, role)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, datetime.now(), role))
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

    async def subscribe_user(self, user_id: int, months: int = 1, provider: str = "yookassa"):
        """Оформить подписку пользователю"""
        end_date = datetime.now() + timedelta(days=30 * months)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users
                SET is_subscribed = TRUE, subscription_end = ?,
                    last_payment_date = ?, payment_provider = ?
                WHERE user_id = ?
            """, (end_date, datetime.now(), provider, user_id))
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

    # Методы для работы с платежами ЮKassa

    async def create_payment(self, user_id: int, amount: int, currency: str = "RUB",
                           payment_id: str = None, invoice_payload: str = None,
                           subscription_months: int = 1) -> str:
        """Создать запись о платеже"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO payments (user_id, payment_id, amount, currency,
                                    invoice_payload, subscription_months)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, payment_id, amount, currency, invoice_payload, subscription_months))
            await db.commit()
            return str(cursor.lastrowid)

    async def get_payment(self, payment_id: str = None, db_id: int = None) -> Optional[dict]:
        """Получить платеж по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if payment_id:
                cursor = await db.execute("""
                    SELECT * FROM payments WHERE payment_id = ?
                """, (payment_id,))
            elif db_id:
                cursor = await db.execute("""
                    SELECT * FROM payments WHERE id = ?
                """, (db_id,))
            else:
                return None

            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_payment_status(self, payment_id: str, status: str,
                                  provider_payment_id: str = None):
        """Обновить статус платежа"""
        async with aiosqlite.connect(self.db_path) as db:
            if provider_payment_id:
                await db.execute("""
                    UPDATE payments
                    SET status = ?, provider_payment_id = ?, completed_at = ?
                    WHERE payment_id = ?
                """, (status, provider_payment_id, datetime.now(), payment_id))
            else:
                await db.execute("""
                    UPDATE payments
                    SET status = ?, completed_at = ?
                    WHERE payment_id = ?
                """, (status, datetime.now(), payment_id))
            await db.commit()

    async def complete_payment(self, payment_id: str, provider_payment_id: str = None):
        """Завершить платеж и активировать подписку"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем информацию о платеже
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT user_id, subscription_months FROM payments
                WHERE payment_id = ?
            """, (payment_id,))
            payment = await cursor.fetchone()

            if not payment:
                return False

            # Обновляем статус платежа
            await db.execute("""
                UPDATE payments
                SET status = 'completed', provider_payment_id = ?, completed_at = ?
                WHERE payment_id = ?
            """, (provider_payment_id, datetime.now(), payment_id))

            # Активируем подписку пользователю
            end_date = datetime.now() + timedelta(days=30 * payment['subscription_months'])
            await db.execute("""
                UPDATE users
                SET is_subscribed = TRUE, subscription_end = ?,
                    last_payment_date = ?, payment_provider = 'yookassa'
                WHERE user_id = ?
            """, (end_date, datetime.now(), payment['user_id']))

            await db.commit()
            return True

    async def get_user_payments(self, user_id: int) -> List[dict]:
        """Получить все платежи пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM payments
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update_payment_status(self, payment_id: str, status: str) -> bool:
        """Обновить статус платежа"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE payments
                SET status = ?
                WHERE payment_id = ?
            """, (status, payment_id))
            await db.commit()
            return cursor.rowcount > 0

    async def get_all_users_for_broadcast(self) -> List[dict]:
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

    # ========== АДМИН МЕТОДЫ ==========

    async def get_admin_user_by_username(self, username: str) -> Optional[dict]:
        """Получить админ пользователя по username"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM admin_users WHERE username = ? AND is_active = TRUE",
                (username,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_admin_user(self, username: str, email: str, password_hash: str,
                               role: str = 'moderator', created_by: int = None) -> int:
        """Создать админ пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO admin_users (username, email, password_hash, role, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (username, email, password_hash, role, created_by))
            await db.commit()
            return cursor.lastrowid

    async def update_admin_user_login(self, user_id: int):
        """Обновить время последнего входа админ пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE admin_users SET last_login = ? WHERE id = ?
            """, (datetime.now(), user_id))
            await db.commit()

    async def get_users_paginated(self, page: int = 1, per_page: int = 50,
                                 search: str = None, filter_type: str = None) -> Dict[str, Any]:
        """Получить пользователей с пагинацией и фильтрацией"""
        offset = (page - 1) * per_page

        # Базовый запрос
        where_conditions = []
        params = []

        if search:
            where_conditions.append("""
                (username LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR CAST(user_id AS TEXT) LIKE ?)
            """)
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])

        if filter_type == 'subscribed':
            where_conditions.append("is_subscribed = TRUE AND subscription_end > ?")
            params.append(datetime.now())
        elif filter_type == 'unlimited':
            where_conditions.append("unlimited_access = TRUE")
        elif filter_type == 'blocked':
            where_conditions.append("blocked = TRUE")
        elif filter_type == 'bot_blocked':
            where_conditions.append("bot_blocked = TRUE")
        elif filter_type == 'active':
            where_conditions.append("blocked = FALSE AND bot_blocked = FALSE")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Получаем общее количество
            count_cursor = await db.execute(f"""
                SELECT COUNT(*) FROM users WHERE {where_clause}
            """, params)
            total = (await count_cursor.fetchone())[0]

            # Получаем пользователей
            cursor = await db.execute(f"""
                SELECT * FROM users WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params + [per_page, offset])

            users = [dict(row) for row in await cursor.fetchall()]

            return {
                'users': users,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }

    async def update_user_permissions(self, user_id: int, unlimited_access: bool = None,
                                    blocked: bool = None, notes: str = None,
                                    blocked_by: int = None) -> bool:
        """Обновить права пользователя"""
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

                if blocked_by is not None:
                    updates.append("blocked_by = ?")
                    params.append(blocked_by)

        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if not updates:
            return False

        params.append(user_id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"""
                UPDATE users SET {', '.join(updates)} WHERE user_id = ?
            """, params)
            await db.commit()
            return True

    async def update_subscription(self, user_id: int, is_subscribed: bool = None,
                                subscription_end: datetime = None) -> bool:
        """Обновить подписку пользователя"""
        updates = []
        params = []

        if is_subscribed is not None:
            updates.append("is_subscribed = ?")
            params.append(is_subscribed)

        if subscription_end is not None:
            updates.append("subscription_end = ?")
            params.append(subscription_end)
        elif is_subscribed is False:
            # Если отменяем подписку, очищаем дату окончания
            updates.append("subscription_end = NULL")

        if not updates:
            return False

        update_query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(update_query, params + [user_id])
            await db.commit()
            return True

    async def reset_user_requests(self, user_id: int) -> bool:
        """Сбросить счетчик запросов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users
                SET requests_used = 0
                WHERE user_id = ?
            """, (user_id,))
            await db.commit()
            return True

    async def get_total_requests_count(self) -> int:
        """Получить общее количество запросов всех пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT SUM(requests_used) FROM users")
            result = await cursor.fetchone()
            return result[0] if result[0] is not None else 0

    async def mark_user_bot_blocked(self, user_id: int) -> bool:
        """Пометить пользователя как заблокировавшего бота"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users
                SET bot_blocked = TRUE, blocked_at = ?
                WHERE user_id = ?
            """, (datetime.now(), user_id))
            await db.commit()
            return True

    async def delete_user(self, user_id: int) -> bool:
        """Удалить пользователя и все связанные данные"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Удаляем связанные запросы
                await db.execute("DELETE FROM requests WHERE user_id = ?", (user_id,))

                # Удаляем пользователя
                cursor = await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

                await db.commit()
                return cursor.rowcount > 0

            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
                return False

    async def bulk_delete_users(self, user_ids: list) -> dict:
        """Массовое удаление пользователей"""
        results = {"success": [], "failed": []}

        for user_id in user_ids:
            try:
                if await self.delete_user(user_id):
                    results["success"].append(user_id)
                else:
                    results["failed"].append(user_id)
            except Exception as e:
                logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
                results["failed"].append(user_id)

        return results

    # ========== ШАБЛОНЫ СООБЩЕНИЙ ==========

    async def create_message_template(self, name: str, content: str, parse_mode: str = 'HTML',
                                    category: str = 'general', created_by: int = None) -> int:
        """Создать шаблон сообщения"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO message_templates (name, content, parse_mode, category, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (name, content, parse_mode, category, created_by))
            await db.commit()
            return cursor.lastrowid

    async def get_message_templates(self, category: str = None, is_active: bool = True) -> List[dict]:
        """Получить шаблоны сообщений"""
        conditions = ["is_active = ?"] if is_active else []
        params = [is_active] if is_active else []

        if category:
            conditions.append("category = ?")
            params.append(category)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(f"""
                SELECT * FROM message_templates WHERE {where_clause}
                ORDER BY created_at DESC
            """, params)
            return [dict(row) for row in await cursor.fetchall()]

    async def get_message_template(self, template_id: int) -> Optional[dict]:
        """Получить шаблон по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM message_templates WHERE id = ?", (template_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_message_template(self, template_id: int, name: str = None,
                                    content: str = None, parse_mode: str = None,
                                    category: str = None, is_active: bool = None) -> bool:
        """Обновить шаблон сообщения"""
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
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now())
        params.append(template_id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"""
                UPDATE message_templates SET {', '.join(updates)} WHERE id = ?
            """, params)
            await db.commit()
            return True

    # ========== РАССЫЛКИ ==========

    async def create_broadcast(self, message_text: str, title: str = None, template_id: int = None,
                             parse_mode: str = 'HTML', target_users: str = 'all',
                             created_by: int = None, scheduled_at: datetime = None) -> int:
        """Создать рассылку"""
        if title is None:
            title = f"Рассылка {target_users}"

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO broadcasts
                (title, message_text, template_id, parse_mode, target_users, created_by, scheduled_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (title, message_text, template_id, parse_mode, target_users, created_by, scheduled_at))
            await db.commit()
            return cursor.lastrowid

    async def get_broadcasts_paginated(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Получить рассылки с пагинацией"""
        offset = (page - 1) * per_page

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Общее количество
            count_cursor = await db.execute("SELECT COUNT(*) FROM broadcasts")
            total = (await count_cursor.fetchone())[0]

            # Рассылки с информацией о создателе
            cursor = await db.execute("""
                SELECT b.*, au.username as created_by_username
                FROM broadcasts b
                LEFT JOIN admin_users au ON b.created_by = au.id
                ORDER BY b.created_at DESC
                LIMIT ? OFFSET ?
            """, (per_page, offset))

            broadcasts = [dict(row) for row in await cursor.fetchall()]

            pages = (total + per_page - 1) // per_page

            return {
                'broadcasts': broadcasts,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': pages,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': pages,
                    'has_prev': page > 1,
                    'has_next': page < pages,
                    'prev_page': page - 1 if page > 1 else None,
                    'next_page': page + 1 if page < pages else None
                }
            }

    async def update_broadcast_stats(self, broadcast_id: int, sent_count: int = None,
                                   failed_count: int = None, completed: bool = None,
                                   started_at: datetime = None, error_message: str = None) -> bool:
        """Обновить статистику рассылки"""
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

        if started_at is not None:
            updates.append("started_at = ?")
            params.append(started_at)

        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if not updates:
            return False

        params.append(broadcast_id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"""
                UPDATE broadcasts SET {', '.join(updates)} WHERE id = ?
            """, params)
            await db.commit()
            return True

    async def get_broadcast_by_id(self, broadcast_id: int) -> dict:
        """Получить рассылку по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM broadcasts WHERE id = ?
            """, (broadcast_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_broadcast_status(self, broadcast_id: int, status: str) -> bool:
        """Обновить статус рассылки"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE broadcasts SET status = ? WHERE id = ?",
                (status, broadcast_id)
            )
            await db.commit()
            return True

    async def get_broadcast_target_users(self, broadcast_id: int) -> List[int]:
        """Получить список пользователей для рассылки"""
        broadcast = await self.get_broadcast_by_id(broadcast_id)
        if not broadcast:
            return []

        target_type = broadcast.get("target_users", "all")

        async with aiosqlite.connect(self.db_path) as db:
            if target_type == "all":
                cursor = await db.execute("SELECT user_id FROM users")
            elif target_type == "subscribers":
                cursor = await db.execute(
                    "SELECT user_id FROM users WHERE is_subscribed = 1"
                )
            elif target_type == "active":
                # Активные за последние 30 дней
                thirty_days_ago = datetime.now() - timedelta(days=30)
                cursor = await db.execute(
                    "SELECT user_id FROM users WHERE last_request > ?",
                    (thirty_days_ago,)
                )
            else:
                # Для кастомных фильтров - пока возвращаем всех
                cursor = await db.execute("SELECT user_id FROM users")

            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def log_broadcast_delivery(self, broadcast_id: int, user_id: int,
                                   status: str, message: str = "", error_details: str = ""):
        """Логировать доставку сообщения"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO broadcast_logs
                (broadcast_id, user_id, status, message, error_details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (broadcast_id, user_id, status, message, error_details, datetime.now()))
            await db.commit()

    async def get_broadcast_logs(self, broadcast_id: int, page: int = 1,
                               per_page: int = 50, status: str = None) -> Dict[str, Any]:
        """Получить логи рассылки с пагинацией"""
        offset = (page - 1) * per_page

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Подсчет общего количества
            count_query = "SELECT COUNT(*) FROM broadcast_logs WHERE broadcast_id = ?"
            count_params = [broadcast_id]

            if status:
                count_query += " AND status = ?"
                count_params.append(status)

            cursor = await db.execute(count_query, count_params)
            total = (await cursor.fetchone())[0]

            # Получение логов
            logs_query = """
                SELECT user_id, status, message, error_details, created_at
                FROM broadcast_logs
                WHERE broadcast_id = ?
            """
            logs_params = [broadcast_id]

            if status:
                logs_query += " AND status = ?"
                logs_params.append(status)

            logs_query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            logs_params.extend([per_page, offset])

            cursor = await db.execute(logs_query, logs_params)
            rows = await cursor.fetchall()

            logs = [dict(row) for row in rows]

            return {
                "logs": logs,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page,
                    "has_prev": page > 1,
                    "has_next": page * per_page < total,
                    "prev_num": page - 1 if page > 1 else None,
                    "next_num": page + 1 if page * per_page < total else None
                }
            }

    async def get_all_broadcast_logs(self, broadcast_id: int) -> List[Dict[str, Any]]:
        """Получить все логи рассылки для экспорта"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT user_id, status, message, error_details, created_at
                FROM broadcast_logs
                WHERE broadcast_id = ?
                ORDER BY created_at DESC
            """, (broadcast_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_target_audience_count(self, target_type: str) -> int:
        """Получить количество пользователей в целевой аудитории"""
        async with aiosqlite.connect(self.db_path) as db:
            if target_type == "all":
                cursor = await db.execute("SELECT COUNT(*) FROM users")
            elif target_type == "subscribers":
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM users WHERE is_subscribed = 1"
                )
            elif target_type == "active":
                thirty_days_ago = datetime.now() - timedelta(days=30)
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM users WHERE last_request > ?",
                    (thirty_days_ago,)
                )
            else:
                cursor = await db.execute("SELECT COUNT(*) FROM users")

            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_broadcast_detailed_stats(self, broadcast_id: int) -> Dict[str, Any]:
        """Получить детальную статистику рассылки"""
        async with aiosqlite.connect(self.db_path) as db:
            # Общая информация о рассылке
            broadcast = await self.get_broadcast_by_id(broadcast_id)

            if not broadcast:
                return {
                    "delivered": 0,
                    "failed": 0,
                    "blocked": 0,
                    "total_recipients": 0,
                    "current_rate": 0,
                    "estimated_time": ""
                }

            # Получаем статистику из таблицы broadcasts
            sent_count = broadcast.get("sent_count", 0)
            failed_count = broadcast.get("failed_count", 0)

            # Также проверяем логи, если они есть
            cursor = await db.execute("""
                SELECT status, COUNT(*) as count
                FROM broadcast_logs
                WHERE broadcast_id = ?
                GROUP BY status
            """, (broadcast_id,))

            status_stats = {}
            for row in await cursor.fetchall():
                status_stats[row[0]] = row[1]

            # Если есть логи, используем их, иначе данные из broadcasts
            delivered = status_stats.get("sent", sent_count)
            failed = status_stats.get("failed", failed_count)
            blocked = status_stats.get("blocked", 0)

            # Получаем общее количество получателей
            total_recipients = await self.get_target_audience_count(
                broadcast.get("target_users", "all")
            )

            # Подсчет скорости отправки
            current_rate = 0
            if broadcast.get("started_at"):
                started_at = broadcast["started_at"]
                if isinstance(started_at, str):
                    started_at = datetime.fromisoformat(started_at)

                elapsed_minutes = (datetime.now() - started_at).total_seconds() / 60
                if elapsed_minutes > 0:
                    current_rate = round(delivered / elapsed_minutes, 1)

            # Оценка оставшегося времени
            estimated_time = ""
            if broadcast.get("status") == "sending":
                remaining = total_recipients - delivered

                if current_rate > 0 and remaining > 0:
                    remaining_minutes = remaining / current_rate
                    if remaining_minutes < 60:
                        estimated_time = f"{int(remaining_minutes)} мин"
                    else:
                        hours = int(remaining_minutes // 60)
                        minutes = int(remaining_minutes % 60)
                        estimated_time = f"{hours}ч {minutes}м"

            return {
                "delivered": delivered,
                "failed": failed,
                "blocked": blocked,
                "total_recipients": total_recipients,
                "current_rate": current_rate,
                "estimated_time": estimated_time
            }

    async def get_broadcasts_stats(self) -> Dict[str, int]:
        """Получить общую статистику рассылок"""
        async with aiosqlite.connect(self.db_path) as db:
            # Подсчет по статусам
            cursor = await db.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'sending' THEN 1 ELSE 0 END) as sending,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM broadcasts
            """)

            row = await cursor.fetchone()
            if row:
                return {
                    "total": row[0] or 0,
                    "completed": row[1] or 0,
                    "sending": row[2] or 0,
                    "pending": row[3] or 0,
                    "failed": row[4] or 0
                }

            return {
                "total": 0,
                "completed": 0,
                "sending": 0,
                "pending": 0,
                "failed": 0
            }

    async def get_broadcasts_list(self) -> List[Dict[str, Any]]:
        """Получить список всех рассылок (устаревший метод)"""
        data = await self.get_broadcasts_paginated(page=1, per_page=1000)
        return data["broadcasts"]

    async def update_user_bot_blocked_status(self, user_id: int, blocked: bool):
        """Обновить статус блокировки пользователем бота"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users SET bot_blocked = ?, blocked_at = ?
                WHERE user_id = ?
            """, (blocked, datetime.now() if blocked else None, user_id))
            await db.commit()

    # ========== ЛОГИРОВАНИЕ ==========

    async def log_admin_action(self, admin_user_id: int, action: str, resource_type: str,
                             resource_id: int = None, details: dict = None,
                             ip_address: str = None, user_agent: str = None):
        """Записать действие админа в лог"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO audit_logs
                (admin_user_id, action, resource_type, resource_id, details, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (admin_user_id, action, resource_type, resource_id,
                  json.dumps(details) if details else None, ip_address, user_agent))
            await db.commit()

    async def get_audit_logs(self, page: int = 1, per_page: int = 50,
                           admin_user_id: int = None, action: str = None) -> Dict[str, Any]:
        """Получить логи действий"""
        offset = (page - 1) * per_page

        conditions = []
        params = []

        if admin_user_id:
            conditions.append("al.admin_user_id = ?")
            params.append(admin_user_id)

        if action:
            conditions.append("al.action = ?")
            params.append(action)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Общее количество
            count_cursor = await db.execute(f"""
                SELECT COUNT(*) FROM audit_logs al WHERE {where_clause}
            """, params)
            total = (await count_cursor.fetchone())[0]

            # Логи с информацией о пользователе
            cursor = await db.execute(f"""
                SELECT al.*, au.username
                FROM audit_logs al
                LEFT JOIN admin_users au ON al.admin_user_id = au.id
                WHERE {where_clause}
                ORDER BY al.created_at DESC
                LIMIT ? OFFSET ?
            """, params + [per_page, offset])

            logs = [dict(row) for row in await cursor.fetchall()]

            return {
                'logs': logs,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }

    # ========== РАСШИРЕННАЯ СТАТИСТИКА ==========

    async def get_detailed_stats(self) -> Dict[str, Any]:
        """Получить детальную статистику для админ-панели"""
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}

            # Статистика пользователей
            cursor = await db.execute("""
                SELECT
                    COUNT(*) as total_users,
                    COUNT(CASE WHEN is_subscribed = TRUE AND subscription_end > ? THEN 1 END) as active_subscribers,
                    COUNT(CASE WHEN unlimited_access = TRUE THEN 1 END) as unlimited_users,
                    COUNT(CASE WHEN blocked = TRUE THEN 1 END) as blocked_users,
                    COUNT(CASE WHEN DATE(created_at) = DATE('now') THEN 1 END) as new_today,
                    COUNT(CASE WHEN DATE(created_at) >= DATE('now', '-7 days') THEN 1 END) as new_week,
                    COUNT(CASE WHEN DATE(created_at) >= DATE('now', '-30 days') THEN 1 END) as new_month
                FROM users
            """, (datetime.now(),))
            user_stats = dict(await cursor.fetchone())
            stats['users'] = user_stats

            # Статистика запросов
            cursor = await db.execute("""
                SELECT
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN DATE(created_at) = DATE('now') THEN 1 END) as requests_today,
                    COUNT(CASE WHEN DATE(created_at) >= DATE('now', '-7 days') THEN 1 END) as requests_week,
                    COUNT(CASE WHEN DATE(created_at) >= DATE('now', '-30 days') THEN 1 END) as requests_month
                FROM requests
            """)
            request_stats = dict(await cursor.fetchone())
            stats['requests'] = request_stats

            # Статистика рассылок
            cursor = await db.execute("""
                SELECT
                    COUNT(*) as total_broadcasts,
                    COUNT(CASE WHEN completed = TRUE THEN 1 END) as completed_broadcasts,
                    SUM(sent_count) as total_sent,
                    SUM(failed_count) as total_failed,
                    COUNT(CASE WHEN DATE(created_at) >= DATE('now', '-30 days') THEN 1 END) as broadcasts_month
                FROM broadcasts
            """)
            broadcast_stats = dict(await cursor.fetchone())
            stats['broadcasts'] = broadcast_stats

            # Топ активных пользователей
            cursor = await db.execute("""
                SELECT user_id, username, first_name, last_name, requests_used
                FROM users
                WHERE requests_used > 0
                ORDER BY requests_used DESC
                LIMIT 10
            """)
            stats['top_users'] = [dict(row) for row in await cursor.fetchall()]

            return stats

    async def get_user_activity_chart_data(self, days: int = 30) -> List[Dict[str, Any]]:
        """Получить данные для графика активности пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT
                    DATE(created_at) as date,
                    COUNT(*) as new_users,
                    0 as requests_count
                FROM users
                WHERE DATE(created_at) >= DATE('now', '-{} days')
                GROUP BY DATE(created_at)

                UNION ALL

                SELECT
                    DATE(created_at) as date,
                    0 as new_users,
                    COUNT(*) as requests_count
                FROM requests
                WHERE DATE(created_at) >= DATE('now', '-{} days')
                GROUP BY DATE(created_at)

                ORDER BY date
            """.format(days, days))

            return [dict(row) for row in await cursor.fetchall()]

    # Методы для работы с аудиторией рассылок
    async def get_users_count(self) -> int:
        """Получить общее количество пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            return (await cursor.fetchone())[0]

    async def get_active_users_count(self) -> int:
        """Получить количество активных пользователей (за последние 30 дней)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE last_request > datetime('now', '-30 days')"
            )
            return (await cursor.fetchone())[0]

    async def get_subscribers_count(self) -> int:
        """Получить количество подписчиков"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE is_subscribed = 1 AND subscription_end > datetime('now')"
            )
            return (await cursor.fetchone())[0]

    async def get_blocked_users_count(self) -> int:
        """Получить количество заблокированных пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE bot_blocked = 1"
            )
            return (await cursor.fetchone())[0]

    async def get_all_users(self, limit: int = 50) -> List[dict]:
        """Получить список всех пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT user_id, first_name, last_name, username, created_at FROM users ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_active_users(self, limit: int = 50) -> List[dict]:
        """Получить список активных пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT user_id, first_name, last_name, username, created_at FROM users WHERE last_request > datetime('now', '-30 days') ORDER BY last_request DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_subscribers(self, limit: int = 50) -> List[dict]:
        """Получить список подписчиков"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT user_id, first_name, last_name, username, created_at FROM users WHERE is_subscribed = 1 AND subscription_end > datetime('now') ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_subscribed_users(self) -> List[dict]:
        """Получить всех подписчиков для рассылки"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT user_id FROM users WHERE is_subscribed = 1 AND subscription_end > datetime('now')"
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_user_role(self, user_id: int) -> str:
        """Получить роль пользователя"""
        from bot.utils.roles import TelegramUserPermissions

        user = await self.get_user(user_id)
        if user and 'role' in user:
            return user['role']

        # Возвращаем роль по умолчанию или предопределенную
        return TelegramUserPermissions.get_user_role(user_id)

    async def update_user_role(self, user_id: int, role: str) -> bool:
        """Обновить роль пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    UPDATE users
                    SET role = ?
                    WHERE user_id = ?
                """, (role, user_id))

                await db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка обновления роли пользователя {user_id}: {e}")
            return False

    async def get_users_by_role(self, role: str) -> List[dict]:
        """Получить пользователей по роли"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE role = ? ORDER BY created_at DESC",
                (role,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_admin_users(self) -> List[dict]:
        """Получить всех администраторов"""
        from bot.utils.roles import RoleHierarchy

        admin_roles = list(RoleHierarchy.ADMIN_ROLES)
        placeholders = ','.join(['?' for _ in admin_roles])

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT * FROM users WHERE role IN ({placeholders}) ORDER BY role, created_at DESC",
                admin_roles
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_active_users_for_broadcast(self, days: int = 30) -> List[dict]:
        """Получить активных пользователей для рассылки"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT user_id FROM users WHERE last_request > datetime('now', '-{} days')".format(days)
            )
            return [dict(row) for row in await cursor.fetchall()]
