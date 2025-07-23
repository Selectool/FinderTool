"""
Модели базы данных
"""
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


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

        # Запускаем миграции для админ-панели
        try:
            from .admin_migrations import run_admin_migrations
            await run_admin_migrations(self.db_path)
        except Exception as e:
            logger.error(f"Ошибка выполнения миграций админ-панели: {e}")

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

        # Проверяем блокировку администратором
        if user.get('blocked', False):
            return False

        # Проверяем, заблокировал ли пользователь бота
        if user.get('bot_blocked', False):
            return False

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

    async def create_broadcast(self, message_text: str, template_id: int = None,
                             parse_mode: str = 'HTML', target_users: str = 'all',
                             created_by: int = None, scheduled_at: datetime = None) -> int:
        """Создать рассылку"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO broadcasts
                (message_text, template_id, parse_mode, target_users, created_by, scheduled_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (message_text, template_id, parse_mode, target_users, created_by, scheduled_at))
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

            return {
                'broadcasts': broadcasts,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
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
