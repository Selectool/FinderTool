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

            query = """
                SELECT * FROM admin_users
                WHERE username = %s AND is_active = TRUE
            """
            if adapter.db_type == 'sqlite':
                query = query.replace('%s', '?')

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

            query = """
                UPDATE admin_users SET last_login = %s WHERE id = %s
            """
            if adapter.db_type == 'sqlite':
                query = query.replace('%s', '?')

            await adapter.execute(query, (datetime.now(), user_id))
            await adapter.disconnect()
        except Exception as e:
            logger.error(f"Ошибка обновления времени входа для пользователя {user_id}: {e}")


# Глобальный экземпляр менеджера
db_manager = ProductionDatabaseManager()


async def init_production_database():
    """Инициализация production-ready базы данных"""
    return await db_manager.optimize_for_production()
