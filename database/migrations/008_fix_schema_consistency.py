"""
Миграция 008: Исправление консистентности схемы БД
Создана: 2025-08-04 22:57:00
Исправляет все проблемы с внешними ключами, недостающими столбцами и несоответствиями схемы
"""
from database.migration_manager import Migration
from database.db_adapter import DatabaseAdapter
import logging

logger = logging.getLogger(__name__)

class Migration008(Migration):
    def __init__(self):
        super().__init__("008", "Исправление консистентности схемы БД (внешние ключи, столбцы)")
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        logger.info("🔧 Начинаем исправление схемы БД...")
        
        try:
            # 1. Добавляем недостающие столбцы в users
            await self._fix_users_table(adapter)
            
            # 2. Добавляем недостающие столбцы в payments
            await self._fix_payments_table(adapter)
            
            # 3. Исправляем внешние ключи
            await self._fix_foreign_keys(adapter)
            
            # 4. Создаем недостающие индексы
            await self._create_missing_indexes(adapter)
            
            logger.info("✅ Схема БД успешно исправлена")
            
        except Exception as e:
            logger.error(f"❌ Ошибка исправления схемы БД: {e}")
            raise
    
    async def _fix_users_table(self, adapter: DatabaseAdapter):
        """Исправить таблицу users"""
        logger.info("🔧 Исправляем таблицу users...")
        
        # Список столбцов для добавления
        columns_to_add = [
            ("subscription_end", "TIMESTAMP"),
            ("last_request", "TIMESTAMP"),
            ("last_payment_date", "TIMESTAMP"),
            ("payment_provider", "TEXT"),
            ("unlimited_access", "BOOLEAN DEFAULT FALSE"),
            ("blocked_at", "TIMESTAMP"),
            ("language_code", "VARCHAR(10) DEFAULT 'ru'"),
            ("is_premium", "BOOLEAN DEFAULT FALSE"),
            ("subscription_active", "BOOLEAN DEFAULT FALSE"),
            ("free_requests_used", "INTEGER DEFAULT 0"),
            ("total_requests", "INTEGER DEFAULT 0"),
            ("last_activity", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("notes", "TEXT"),
            ("blocked_by", "INTEGER"),
            ("referrer_id", "INTEGER"),
            ("registration_source", "VARCHAR(100) DEFAULT 'bot'")
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                await adapter.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
                logger.info(f"✅ Добавлен столбец users.{column_name}")
            except Exception as e:
                if any(phrase in str(e).lower() for phrase in ["already exists", "duplicate column", "column already exists"]):
                    logger.info(f"ℹ️ Столбец users.{column_name} уже существует")
                else:
                    logger.warning(f"⚠️ Ошибка добавления столбца users.{column_name}: {e}")
    
    async def _fix_payments_table(self, adapter: DatabaseAdapter):
        """Исправить таблицу payments"""
        logger.info("🔧 Исправляем таблицу payments...")
        
        # Список столбцов для добавления
        columns_to_add = [
            ("provider", "TEXT DEFAULT 'yookassa'"),
            ("payment_method", "VARCHAR(100)"),
            ("metadata", "JSONB" if adapter.db_type == 'postgresql' else "TEXT")
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                await adapter.execute(f"ALTER TABLE payments ADD COLUMN {column_name} {column_def}")
                logger.info(f"✅ Добавлен столбец payments.{column_name}")
            except Exception as e:
                if any(phrase in str(e).lower() for phrase in ["already exists", "duplicate column", "column already exists"]):
                    logger.info(f"ℹ️ Столбец payments.{column_name} уже существует")
                else:
                    logger.warning(f"⚠️ Ошибка добавления столбца payments.{column_name}: {e}")
    
    async def _fix_foreign_keys(self, adapter: DatabaseAdapter):
        """Исправить внешние ключи"""
        logger.info("🔧 Исправляем внешние ключи...")
        
        if adapter.db_type == 'postgresql':
            # Проверяем и исправляем внешние ключи
            foreign_keys_to_check = [
                ("requests", "user_id", "users", "user_id"),
                ("payments", "user_id", "users", "user_id"),
                ("broadcast_logs", "broadcast_id", "broadcast_messages", "id"),
                ("scheduled_broadcasts", "template_id", "message_templates", "id"),
                ("scheduled_broadcasts", "created_by", "admin_users", "id"),
                ("audit_logs", "admin_user_id", "admin_users", "id")
            ]
            
            for table, column, ref_table, ref_column in foreign_keys_to_check:
                try:
                    # Проверяем существование таблиц и столбцов
                    table_exists = await self._table_exists(adapter, table)
                    ref_table_exists = await self._table_exists(adapter, ref_table)
                    
                    if table_exists and ref_table_exists:
                        # Проверяем существование внешнего ключа
                        fk_exists = await self._foreign_key_exists(adapter, table, column, ref_table, ref_column)
                        if not fk_exists:
                            # Создаем внешний ключ
                            constraint_name = f"fk_{table}_{column}_{ref_table}_{ref_column}"
                            await adapter.execute(f"""
                                ALTER TABLE {table} 
                                ADD CONSTRAINT {constraint_name} 
                                FOREIGN KEY ({column}) REFERENCES {ref_table} ({ref_column})
                            """)
                            logger.info(f"✅ Создан внешний ключ {constraint_name}")
                        else:
                            logger.info(f"ℹ️ Внешний ключ {table}.{column} -> {ref_table}.{ref_column} уже существует")
                    else:
                        logger.warning(f"⚠️ Таблица {table} или {ref_table} не существует")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка создания внешнего ключа {table}.{column}: {e}")
    
    async def _create_missing_indexes(self, adapter: DatabaseAdapter):
        """Создать недостающие индексы"""
        logger.info("🔧 Создаем недостающие индексы...")
        
        indexes = [
            # Пользователи
            ("idx_users_created_at", "users", "created_at"),
            ("idx_users_subscription", "users", "is_subscribed"),
            ("idx_users_role", "users", "role"),
            ("idx_users_blocked", "users", "blocked"),
            ("idx_users_last_activity", "users", "last_activity"),
            
            # Запросы
            ("idx_requests_user_created", "requests", "user_id, created_at"),
            ("idx_requests_created_at", "requests", "created_at"),
            
            # Платежи
            ("idx_payments_user_id", "payments", "user_id"),
            ("idx_payments_status", "payments", "status"),
            ("idx_payments_created_at", "payments", "created_at"),
            ("idx_payments_payment_id", "payments", "payment_id"),
            
            # Рассылки
            ("idx_broadcasts_status", "broadcast_messages", "sent_count"),
            ("idx_broadcasts_created_at", "broadcast_messages", "created_at"),
            
            # Админ-пользователи
            ("idx_admin_users_username", "admin_users", "username"),
            ("idx_admin_users_email", "admin_users", "email"),
            ("idx_admin_users_role", "admin_users", "role"),
            
            # Логи аудита
            ("idx_audit_logs_admin_user", "audit_logs", "admin_user_id"),
            ("idx_audit_logs_created_at", "audit_logs", "created_at"),
            ("idx_audit_logs_action", "audit_logs", "action")
        ]
        
        for index_name, table_name, columns in indexes:
            try:
                # Проверяем существование таблицы
                table_exists = await self._table_exists(adapter, table_name)
                if table_exists:
                    await adapter.execute(f"""
                        CREATE INDEX IF NOT EXISTS {index_name} 
                        ON {table_name} ({columns})
                    """)
                    logger.info(f"✅ Создан индекс {index_name}")
                else:
                    logger.warning(f"⚠️ Таблица {table_name} не существует, пропускаем индекс {index_name}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка создания индекса {index_name}: {e}")
    
    async def _table_exists(self, adapter: DatabaseAdapter, table_name: str) -> bool:
        """Проверить существование таблицы"""
        try:
            if adapter.db_type == 'postgresql':
                result = await adapter.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = $1
                    )
                """, (table_name,))
                return bool(result)
            else:  # SQLite
                result = await adapter.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table_name,))
                return result is not None
        except Exception:
            return False
    
    async def _foreign_key_exists(self, adapter: DatabaseAdapter, table: str, column: str, ref_table: str, ref_column: str) -> bool:
        """Проверить существование внешнего ключа"""
        try:
            if adapter.db_type == 'postgresql':
                result = await adapter.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                        JOIN information_schema.constraint_column_usage ccu 
                        ON ccu.constraint_name = tc.constraint_name
                        WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_name = $1
                        AND kcu.column_name = $2
                        AND ccu.table_name = $3
                        AND ccu.column_name = $4
                    )
                """, (table, column, ref_table, ref_column))
                return bool(result)
            return False  # Для SQLite не проверяем
        except Exception:
            return False
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        logger.warning("⚠️ Откат миграции 008 не реализован - слишком много изменений")
        # Откат этой миграции слишком сложен и может повредить данные
        pass

# Экспортируем класс для менеджера миграций
Migration = Migration008
