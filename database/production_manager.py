"""
Production-ready менеджер базы данных для автоматической инициализации и миграции
"""
import os
import asyncio
import logging
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from .db_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class ProductionDatabaseManager:
    """Production-ready менеджер для автоматической инициализации БД"""

    def __init__(self, db_path: str = "bot.db"):
        self.legacy_db_path = db_path  # Для совместимости
        self.db_path = db_path  # Добавляем для совместимости с админ-панелью
        self.database_url = self._get_database_url()
        self.adapter = DatabaseAdapter(self.database_url)
        self.migration_lock_file = "database/.migration_lock"
        self.backup_dir = Path("database/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Метрики
        self.query_stats = {}

    def _get_database_url(self) -> str:
        """Получить URL базы данных из переменных окружения"""
        # Приоритет: DATABASE_URL -> локальная SQLite
        database_url = os.getenv('DATABASE_URL')

        if database_url:
            logger.info(f"Используется PostgreSQL: {database_url.split('@')[0]}@***")
            return database_url
        else:
            logger.info("Используется локальная SQLite база данных")
            return f"sqlite:///{self.legacy_db_path}"

    async def initialize_database(self) -> bool:
        """
        Автоматическая инициализация базы данных
        Возвращает True если инициализация прошла успешно
        """
        try:
            logger.info("Начинаем инициализацию базы данных...")

            # Проверяем подключение
            await self._check_connection()

            # Создаем таблицы если их нет
            await self._ensure_tables_exist()

            # Выполняем миграцию если необходимо
            migration_needed = await self._check_migration_needed()
            if migration_needed:
                await self._perform_migration()

            # Создаем индексы для оптимизации
            await self._create_indexes()

            logger.info("База данных успешно инициализирована")
            return True

        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            return False

    async def _check_connection(self):
        """Проверить подключение к базе данных"""
        try:
            await self.adapter.connect()

            # Простой тест подключения
            await self.adapter.execute("SELECT 1")

            logger.info("Подключение к базе данных установлено")

        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            raise
        finally:
            await self.adapter.disconnect()

    async def _ensure_tables_exist(self):
        """Убедиться что все необходимые таблицы существуют"""
        try:
            await self.adapter.connect()
            await self.adapter.create_tables_if_not_exist()
            logger.info("Таблицы базы данных проверены/созданы")

        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise
        finally:
            await self.adapter.disconnect()

    async def _check_migration_needed(self) -> bool:
        """
        Проверить нужна ли миграция данных из SQLite в PostgreSQL
        """
        # Миграция нужна если:
        # 1. Используется PostgreSQL
        # 2. Существует файл SQLite с данными
        # 3. Миграция еще не выполнялась

        if self.adapter.db_type != 'postgresql':
            return False

        # Проверяем существование SQLite файла
        sqlite_file = self.legacy_db_path
        if not os.path.exists(sqlite_file):
            logger.info("SQLite файл не найден, миграция не требуется")
            return False

        # Проверяем блокировку миграции
        if os.path.exists(self.migration_lock_file):
            logger.info("Миграция уже выполнена ранее")
            return False

        # Проверяем есть ли данные в SQLite
        try:
            sqlite_adapter = DatabaseAdapter(f"sqlite:///{sqlite_file}")
            await sqlite_adapter.connect()

            users = await sqlite_adapter.fetch_all("SELECT COUNT(*) as count FROM users")
            user_count = users[0]['count'] if users else 0

            await sqlite_adapter.disconnect()

            if user_count > 0:
                logger.info(f"Найдено {user_count} пользователей в SQLite, требуется миграция")
                return True
            else:
                logger.info("SQLite база пуста, миграция не требуется")
                return False

        except Exception as e:
            logger.warning(f"Ошибка проверки SQLite данных: {e}")
            return False

    async def _perform_migration(self):
        """Выполнить миграцию данных"""
        try:
            logger.info("Начинаем автоматическую миграцию данных...")

            # Создаем резервную копию
            await self._create_backup()

            # Импортируем и выполняем миграцию
            from scripts.migrate_to_postgresql import DataMigrator

            sqlite_url = f"sqlite:///{self.legacy_db_path}"
            migrator = DataMigrator(sqlite_url, self.database_url)

            # Выполняем миграцию
            await migrator.migrate_all_data()

            # Создаем файл блокировки
            await self._create_migration_lock()

            logger.info("Миграция данных завершена успешно")

        except Exception as e:
            logger.error(f"Ошибка миграции данных: {e}")
            # Не прерываем работу бота из-за ошибки миграции
            # Просто логируем и продолжаем с пустой PostgreSQL базой

    async def _create_backup(self):
        """Создать резервную копию данных"""
        try:
            # Создаем бэкап SQLite файла если он существует
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"bot_backup_{timestamp}.db"

            if os.path.exists(self.legacy_db_path):
                shutil.copy2(self.legacy_db_path, backup_file)
                logger.info(f"Создана резервная копия: {backup_file}")

        except Exception as e:
            logger.warning(f"Ошибка создания резервной копии: {e}")

    async def _create_migration_lock(self):
        """Создать файл блокировки миграции"""
        try:
            os.makedirs(os.path.dirname(self.migration_lock_file), exist_ok=True)

            lock_data = {
                "migration_date": datetime.now().isoformat(),
                "database_url": self.database_url.split('@')[0] + "@***" if '@' in self.database_url else self.database_url,
                "status": "completed"
            }

            with open(self.migration_lock_file, 'w', encoding='utf-8') as f:
                json.dump(lock_data, f, indent=2)

            logger.info("Создан файл блокировки миграции")

        except Exception as e:
            logger.warning(f"Ошибка создания файла блокировки: {e}")

    async def _create_indexes(self):
        """Создать индексы для оптимизации производительности"""
        indexes = [
            # Пользователи
            "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(is_subscribed, subscription_end)",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            "CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(blocked, bot_blocked)",

            # Запросы
            "CREATE INDEX IF NOT EXISTS idx_requests_user_created ON requests(user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at)",

            # Платежи
            "CREATE INDEX IF NOT EXISTS idx_payments_user_status ON payments(user_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_payments_status_created ON payments(status, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_payments_provider ON payments(provider, status)",

            # Рассылки
            "CREATE INDEX IF NOT EXISTS idx_broadcasts_status_created ON broadcasts(status, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_broadcasts_created_by ON broadcasts(created_by, created_at)",

            # Админ пользователи
            "CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_admin_users_last_login ON admin_users(last_login)",
        ]

        try:
            await self.adapter.connect()

            for index_sql in indexes:
                try:
                    await self.adapter.execute(index_sql)
                    logger.debug(f"Создан индекс: {index_sql.split('ON')[1].split('(')[0].strip()}")
                except Exception as e:
                    logger.warning(f"Ошибка создания индекса: {e}")

            logger.info("Индексы базы данных созданы/обновлены")

        except Exception as e:
            logger.error(f"Ошибка создания индексов: {e}")
        finally:
            await self.adapter.disconnect()

    async def get_database_info(self) -> Dict[str, Any]:
        """Получить информацию о базе данных"""
        try:
            await self.adapter.connect()

            info = {
                "database_type": self.adapter.db_type,
                "database_url": self.database_url.split('@')[0] + "@***" if '@' in self.database_url else self.database_url,
                "connection_status": "connected"
            }

            # Получаем статистику таблиц
            if self.adapter.db_type == 'postgresql':
                tables_info = await self.adapter.fetch_all("""
                    SELECT table_name,
                           (SELECT COUNT(*) FROM information_schema.columns
                            WHERE table_name = t.table_name) as column_count
                    FROM information_schema.tables t
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """)
            else:
                tables_info = await self.adapter.fetch_all("""
                    SELECT name as table_name FROM sqlite_master
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)

            info["tables"] = [dict(table) for table in tables_info] if tables_info else []

            # Получаем количество записей в основных таблицах
            tables = ['users', 'requests', 'payments', 'broadcasts']
            for table in tables:
                try:
                    result = await self.adapter.fetch_all(f"SELECT COUNT(*) as count FROM {table}")
                    info[f'{table}_count'] = result[0]['count'] if result else 0
                except:
                    info[f'{table}_count'] = 0

            return info

        except Exception as e:
            return {
                "database_type": self.adapter.db_type,
                "connection_status": "error",
                "error": str(e)
            }
        finally:
            await self.adapter.disconnect()

    async def cleanup_old_backups(self, keep_days: int = 30):
        """Очистка старых бэкапов"""
        cutoff_date = datetime.now() - timedelta(days=keep_days)

        for backup_file in self.backup_dir.glob("bot_backup_*.db"):
            if backup_file.stat().st_mtime < cutoff_date.timestamp():
                try:
                    backup_file.unlink()
                    logger.info(f"Удален старый бэкап: {backup_file}")
                except Exception as e:
                    logger.error(f"Ошибка удаления бэкапа {backup_file}: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья базы данных"""
        health = {
            'status': 'healthy',
            'checks': {},
            'timestamp': datetime.now().isoformat()
        }

        try:
            # Проверка подключения
            await self.adapter.connect()
            await self.adapter.execute("SELECT 1")
            health['checks']['connection'] = 'ok'

            # Проверка доступности записи
            if self.adapter.db_type == 'postgresql':
                await self.adapter.execute("CREATE TEMP TABLE test_write (id INTEGER)")
                await self.adapter.execute("DROP TABLE test_write")
            else:
                await self.adapter.execute("CREATE TEMP TABLE test_write (id INTEGER)")
                await self.adapter.execute("DROP TABLE test_write")
            health['checks']['write_access'] = 'ok'

            # Информация о базе данных
            health['checks']['database_type'] = self.adapter.db_type

        except Exception as e:
            health['status'] = 'unhealthy'
            health['error'] = str(e)
            logger.error(f"Проблема с базой данных: {e}")
        finally:
            await self.adapter.disconnect()

        return health

    async def optimize_for_production(self):
        """Полная оптимизация для продакшн"""
        logger.info("Начинаем оптимизацию базы данных для продакшн...")

        # Инициализируем базу данных
        success = await self.initialize_database()
        if not success:
            logger.error("Ошибка инициализации базы данных")
            return None

        # Получаем информацию о базе данных
        info = await self.get_database_info()
        logger.info(f"Информация о БД: {json.dumps(info, indent=2, default=str)}")

        # Очищаем старые бэкапы
        await self.cleanup_old_backups()

        logger.info("Оптимизация базы данных завершена")

        return info

    # ========== АДМИН МЕТОДЫ ==========

    async def get_admin_user_by_username(self, username: str) -> Optional[dict]:
        """Получить админ пользователя по username"""
        try:
            # Создаем новое подключение для каждого запроса
            adapter = DatabaseAdapter(self.database_url)
            await adapter.connect()

            if adapter.db_type == 'sqlite':
                query = """
                    SELECT * FROM admin_users
                    WHERE username = ? AND is_active = TRUE
                """
            else:  # PostgreSQL
                query = """
                    SELECT * FROM admin_users
                    WHERE username = $1 AND is_active = TRUE
                """

            result = await adapter.fetch_one(query, (username,))
            await adapter.disconnect()
            return result
        except Exception as e:
            logger.error(f"Ошибка получения админ пользователя {username}: {e}")
            return None

    async def update_admin_user_login(self, user_id: int):
        """Обновить время последнего входа админ пользователя"""
        try:
            # Создаем новое подключение для каждого запроса
            adapter = DatabaseAdapter(self.database_url)
            await adapter.connect()

            if adapter.db_type == 'sqlite':
                query = """
                    UPDATE admin_users SET last_login = ? WHERE id = ?
                """
            else:  # PostgreSQL
                query = """
                    UPDATE admin_users SET last_login = $1 WHERE id = $2
                """

            await adapter.execute(query, (datetime.now(), user_id))
            await adapter.disconnect()
        except Exception as e:
            logger.error(f"Ошибка обновления времени входа для пользователя {user_id}: {e}")

    async def log_admin_action(self, admin_user_id: int, action: str, resource_type: str,
                             resource_id: int = None, details: dict = None,
                             ip_address: str = None, user_agent: str = None):
        """Записать действие админа в лог"""
        try:
            import json
            # Создаем новое подключение для каждого запроса
            adapter = DatabaseAdapter(self.database_url)
            await adapter.connect()

            if adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO audit_logs
                    (admin_user_id, action, resource_type, resource_id, details, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
            else:  # PostgreSQL
                query = """
                    INSERT INTO audit_logs
                    (admin_user_id, action, resource_type, resource_id, details, ip_address, user_agent)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """

            await adapter.execute(query, (
                admin_user_id, action, resource_type, resource_id,
                json.dumps(details) if details else None, ip_address, user_agent
            ))
            await adapter.disconnect()

            logger.info(f"Logged admin action: {action} on {resource_type} by admin {admin_user_id}")
        except Exception as e:
            logger.error(f"Ошибка логирования действия админа: {e}")
            # Не прерываем выполнение из-за ошибки логирования

    async def get_users_paginated(self, page: int = 1, per_page: int = 50,
                                 search: str = None, filter_type: str = None) -> Dict[str, Any]:
        """Получить пользователей с пагинацией и фильтрацией"""
        try:
            adapter = DatabaseAdapter(self.database_url)
            await adapter.connect()

            offset = (page - 1) * per_page

            # Базовый запрос
            where_conditions = []
            params = []

            if search:
                if adapter.db_type == 'sqlite':
                    where_conditions.append("""
                        (username LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR CAST(user_id AS TEXT) LIKE ?)
                    """)
                    search_param = f"%{search}%"
                    params.extend([search_param, search_param, search_param, search_param])
                else:  # PostgreSQL
                    where_conditions.append("""
                        (username ILIKE $%d OR first_name ILIKE $%d OR last_name ILIKE $%d OR CAST(user_id AS TEXT) ILIKE $%d)
                    """ % (len(params)+1, len(params)+2, len(params)+3, len(params)+4))
                    search_param = f"%{search}%"
                    params.extend([search_param, search_param, search_param, search_param])

            if filter_type:
                if filter_type == "subscribed":
                    where_conditions.append("is_subscribed = TRUE")
                elif filter_type == "unlimited":
                    where_conditions.append("unlimited_access = TRUE")
                elif filter_type == "blocked":
                    where_conditions.append("blocked = TRUE")
                elif filter_type == "bot_blocked":
                    where_conditions.append("bot_blocked = TRUE")
                elif filter_type == "active":
                    where_conditions.append("last_activity > datetime('now', '-30 days')")

            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            # Общее количество
            count_query = f"SELECT COUNT(*) FROM users WHERE {where_clause}"
            total = await adapter.fetch_one(count_query, params)
            total = total[0] if total else 0

            # Пользователи
            if adapter.db_type == 'sqlite':
                users_query = f"""
                    SELECT * FROM users
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                params.extend([per_page, offset])
            else:  # PostgreSQL
                users_query = f"""
                    SELECT * FROM users
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${len(params)+1} OFFSET ${len(params)+2}
                """
                params.extend([per_page, offset])

            users = await adapter.fetch_all(users_query, params)

            await adapter.disconnect()

            return {
                "users": [dict(user) for user in users] if users else [],
                "total": total,
                "page": page,
                "per_page": per_page,
                "pagination": {
                    "current_page": page,
                    "total_pages": (total + per_page - 1) // per_page,
                    "has_prev": page > 1,
                    "has_next": page * per_page < total,
                    "prev_page": page - 1 if page > 1 else None,
                    "next_page": page + 1 if page * per_page < total else None
                }
            }
        except Exception as e:
            logger.error(f"Ошибка получения пользователей: {e}")
            return {"users": [], "total": 0, "page": page, "per_page": per_page, "pagination": {}}

    async def get_broadcasts_paginated(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Получить рассылки с пагинацией"""
        try:
            adapter = DatabaseAdapter(self.database_url)
            await adapter.connect()

            offset = (page - 1) * per_page

            # Общее количество
            count_query = "SELECT COUNT(*) FROM broadcasts"
            total = await adapter.fetch_one(count_query)
            total = total[0] if total else 0

            # Рассылки с информацией о создателе
            if adapter.db_type == 'sqlite':
                broadcasts_query = """
                    SELECT b.*, au.username as created_by_username
                    FROM broadcasts b
                    LEFT JOIN admin_users au ON b.created_by = au.id
                    ORDER BY b.created_at DESC
                    LIMIT ? OFFSET ?
                """
                params = [per_page, offset]
            else:  # PostgreSQL
                broadcasts_query = """
                    SELECT b.*, au.username as created_by_username
                    FROM broadcasts b
                    LEFT JOIN admin_users au ON b.created_by = au.id
                    ORDER BY b.created_at DESC
                    LIMIT $1 OFFSET $2
                """
                params = [per_page, offset]

            broadcasts = await adapter.fetch_all(broadcasts_query, params)

            await adapter.disconnect()

            return {
                "broadcasts": [dict(broadcast) for broadcast in broadcasts] if broadcasts else [],
                "total": total,
                "page": page,
                "per_page": per_page,
                "pagination": {
                    "current_page": page,
                    "total_pages": (total + per_page - 1) // per_page,
                    "has_prev": page > 1,
                    "has_next": page * per_page < total,
                    "prev_page": page - 1 if page > 1 else None,
                    "next_page": page + 1 if page * per_page < total else None
                }
            }
        except Exception as e:
            logger.error(f"Ошибка получения рассылок: {e}")
            return {"broadcasts": [], "total": 0, "page": page, "per_page": per_page, "pagination": {}}

    async def get_broadcasts_stats(self) -> Dict[str, Any]:
        """Получить статистику рассылок"""
        try:
            adapter = DatabaseAdapter(self.database_url)
            await adapter.connect()

            stats = {}

            # Общее количество рассылок
            total_query = "SELECT COUNT(*) FROM broadcasts"
            total = await adapter.fetch_one(total_query)
            stats['total'] = total[0] if total else 0

            # Рассылки по статусам
            status_query = """
                SELECT status, COUNT(*) as count
                FROM broadcasts
                GROUP BY status
            """
            status_results = await adapter.fetch_all(status_query)
            stats['by_status'] = {row[0]: row[1] for row in status_results} if status_results else {}

            await adapter.disconnect()
            return stats
        except Exception as e:
            logger.error(f"Ошибка получения статистики рассылок: {e}")
            return {"total": 0, "by_status": {}}


# Глобальный экземпляр менеджера
db_manager = ProductionDatabaseManager()


async def init_production_database():
    """Инициализация production-ready базы данных"""
    return await db_manager.optimize_for_production()
