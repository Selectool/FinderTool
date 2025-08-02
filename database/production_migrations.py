"""
Production миграции для обеспечения полной схемы PostgreSQL
Исправляет проблему отсутствующих таблиц admin_users и других
"""
import logging
from database.db_adapter import DatabaseAdapter
from database.production_manager import ProductionDatabaseManager
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

class ProductionMigrations:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    async def run_critical_migrations(self):
        """Выполнить критически важные миграции для production"""
        logger.info("🚀 Запуск критических миграций для production...")
        
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            # Создаем таблицу admin_users (критически важно!)
            await self._create_admin_users_table(adapter)
            
            # Создаем остальные критически важные таблицы
            await self._create_roles_table(adapter)
            await self._create_message_templates_table(adapter)
            await self._create_scheduled_broadcasts_table(adapter)
            await self._create_audit_logs_table(adapter)
            await self._create_ab_tests_table(adapter)
            await self._create_broadcast_logs_table(adapter)
            await self._create_user_permissions_table(adapter)
            
            # Расширяем существующие таблицы
            await self._extend_users_table(adapter)
            await self._extend_broadcasts_table(adapter)
            
            # Вставляем данные по умолчанию
            await self._insert_default_roles(adapter)
            await self._create_default_admin_user(adapter)
            await self._assign_default_telegram_roles(adapter)
            
            logger.info("✅ Все критические миграции выполнены")
                
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения миграций: {e}")
            raise
        finally:
            await adapter.disconnect()
    
    async def _create_admin_users_table(self, adapter: DatabaseAdapter):
        """Создать таблицу админ пользователей"""
        logger.info("Создание таблицы admin_users...")
        query = """
            CREATE TABLE IF NOT EXISTS admin_users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role VARCHAR(100) NOT NULL DEFAULT 'moderator',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                created_by INTEGER,
                FOREIGN KEY (created_by) REFERENCES admin_users (id)
            )
        """
        await adapter.execute(query)
        logger.info("✅ Таблица admin_users создана")
    
    async def _create_roles_table(self, adapter: DatabaseAdapter):
        """Создать таблицу ролей"""
        logger.info("Создание таблицы roles...")
        query = """
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                display_name VARCHAR(255) NOT NULL,
                permissions TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        await adapter.execute(query)
        logger.info("✅ Таблица roles создана")
    
    async def _create_message_templates_table(self, adapter: DatabaseAdapter):
        """Создать таблицу шаблонов сообщений"""
        logger.info("Создание таблицы message_templates...")
        query = """
            CREATE TABLE IF NOT EXISTS message_templates (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                parse_mode VARCHAR(50) DEFAULT 'HTML',
                category VARCHAR(100) DEFAULT 'general',
                is_active BOOLEAN DEFAULT TRUE,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES admin_users (id)
            )
        """
        await adapter.execute(query)
        logger.info("✅ Таблица message_templates создана")
    
    async def _create_scheduled_broadcasts_table(self, adapter: DatabaseAdapter):
        """Создать таблицу планировщика рассылок"""
        logger.info("Создание таблицы scheduled_broadcasts...")
        query = """
            CREATE TABLE IF NOT EXISTS scheduled_broadcasts (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                template_id INTEGER,
                message_text TEXT,
                parse_mode VARCHAR(50) DEFAULT 'HTML',
                scheduled_at TIMESTAMP NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                target_users VARCHAR(100) DEFAULT 'all',
                sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (template_id) REFERENCES message_templates (id),
                FOREIGN KEY (created_by) REFERENCES admin_users (id)
            )
        """
        await adapter.execute(query)
        logger.info("✅ Таблица scheduled_broadcasts создана")
    
    async def _create_audit_logs_table(self, adapter: DatabaseAdapter):
        """Создать таблицу логов действий"""
        logger.info("Создание таблицы audit_logs...")
        query = """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                admin_user_id INTEGER,
                action VARCHAR(255) NOT NULL,
                resource_type VARCHAR(100) NOT NULL,
                resource_id INTEGER,
                details TEXT,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (admin_user_id) REFERENCES admin_users (id)
            )
        """
        await adapter.execute(query)
        logger.info("✅ Таблица audit_logs создана")
    
    async def _create_ab_tests_table(self, adapter: DatabaseAdapter):
        """Создать таблицу A/B тестов"""
        logger.info("Создание таблицы ab_tests...")
        query = """
            CREATE TABLE IF NOT EXISTS ab_tests (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                variant_a_content TEXT NOT NULL,
                variant_b_content TEXT NOT NULL,
                target_users VARCHAR(100) DEFAULT 'all',
                status VARCHAR(50) DEFAULT 'draft',
                variant_a_sent INTEGER DEFAULT 0,
                variant_b_sent INTEGER DEFAULT 0,
                variant_a_clicks INTEGER DEFAULT 0,
                variant_b_clicks INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES admin_users (id)
            )
        """
        await adapter.execute(query)
        logger.info("✅ Таблица ab_tests создана")
    
    async def _create_broadcast_logs_table(self, adapter: DatabaseAdapter):
        """Создать таблицу логов рассылок"""
        logger.info("Создание таблицы broadcast_logs...")
        query = """
            CREATE TABLE IF NOT EXISTS broadcast_logs (
                id SERIAL PRIMARY KEY,
                broadcast_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                status VARCHAR(50) NOT NULL,
                message TEXT,
                error_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (broadcast_id) REFERENCES broadcast_messages (id)
            )
        """
        await adapter.execute(query)
        
        # Создаем индексы
        await adapter.execute("""
            CREATE INDEX IF NOT EXISTS idx_broadcast_logs_broadcast_id
            ON broadcast_logs (broadcast_id)
        """)
        await adapter.execute("""
            CREATE INDEX IF NOT EXISTS idx_broadcast_logs_status
            ON broadcast_logs (broadcast_id, status)
        """)
        logger.info("✅ Таблица broadcast_logs создана")
    
    async def _create_user_permissions_table(self, adapter: DatabaseAdapter):
        """Создать таблицу прав доступа пользователей"""
        logger.info("Создание таблицы user_permissions...")
        query = """
            CREATE TABLE IF NOT EXISTS user_permissions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                permission VARCHAR(255) NOT NULL,
                granted_by INTEGER,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES admin_users (id),
                FOREIGN KEY (granted_by) REFERENCES admin_users (id),
                UNIQUE(user_id, permission)
            )
        """
        await adapter.execute(query)
        logger.info("✅ Таблица user_permissions создана")
    
    async def _extend_users_table(self, adapter: DatabaseAdapter):
        """Расширить таблицу пользователей"""
        logger.info("Расширение таблицы users...")
        columns_to_add = [
            ("role", "VARCHAR(100) DEFAULT 'user'"),
            ("unlimited_access", "BOOLEAN DEFAULT FALSE"),
            ("notes", "TEXT"),
            ("blocked", "BOOLEAN DEFAULT FALSE"),
            ("bot_blocked", "BOOLEAN DEFAULT FALSE"),
            ("blocked_at", "TIMESTAMP"),
            ("blocked_by", "INTEGER"),
            ("referrer_id", "INTEGER"),
            ("registration_source", "VARCHAR(100) DEFAULT 'bot'")
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                await adapter.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
                logger.info(f"✅ Добавлена колонка {column_name}")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    logger.debug(f"Колонка {column_name} уже существует")
                else:
                    logger.warning(f"Ошибка добавления колонки {column_name}: {e}")
    
    async def _extend_broadcasts_table(self, adapter: DatabaseAdapter):
        """Расширить таблицу рассылок"""
        logger.info("Расширение таблицы broadcast_messages...")
        columns_to_add = [
            ("template_id", "INTEGER"),
            ("parse_mode", "VARCHAR(50) DEFAULT 'HTML'"),
            ("target_users", "VARCHAR(100) DEFAULT 'all'"),
            ("created_by", "INTEGER"),
            ("ab_test_id", "INTEGER"),
            ("scheduled_at", "TIMESTAMP"),
            ("started_at", "TIMESTAMP"),
            ("error_message", "TEXT")
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                await adapter.execute(f"ALTER TABLE broadcast_messages ADD COLUMN {column_name} {column_def}")
                logger.info(f"✅ Добавлена колонка {column_name}")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    logger.debug(f"Колонка {column_name} уже существует")
                else:
                    logger.warning(f"Ошибка добавления колонки {column_name}: {e}")
    
    async def _insert_default_roles(self, adapter: DatabaseAdapter):
        """Вставить роли по умолчанию"""
        logger.info("Вставка ролей по умолчанию...")
        roles = [
            {
                'name': 'super_admin',
                'display_name': 'Супер Администратор',
                'permissions': '["*"]',
                'description': 'Полный доступ ко всем функциям системы'
            },
            {
                'name': 'admin',
                'display_name': 'Администратор',
                'permissions': '["users.view", "users.edit", "broadcasts.create", "broadcasts.send", "statistics.view", "templates.manage"]',
                'description': 'Управление пользователями и рассылками'
            },
            {
                'name': 'developer',
                'display_name': 'Разработчик',
                'permissions': '["statistics.view", "broadcasts.create", "templates.manage", "system.logs"]',
                'description': 'Доступ к статистике и тестированию'
            },
            {
                'name': 'moderator',
                'display_name': 'Модератор',
                'permissions': '["users.view", "statistics.view"]',
                'description': 'Только просмотр данных'
            }
        ]
        
        for role in roles:
            query = """
                INSERT INTO roles (name, display_name, permissions, description)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (name) DO NOTHING
            """
            await adapter.execute(query, (role['name'], role['display_name'], role['permissions'], role['description']))
        
        logger.info("✅ Роли по умолчанию вставлены")
    
    async def _create_default_admin_user(self, adapter: DatabaseAdapter):
        """Создать пользователя админа по умолчанию"""
        logger.info("Создание админ пользователя по умолчанию...")
        
        # Проверяем, есть ли уже админ пользователи
        result = await adapter.fetch_one("SELECT COUNT(*) FROM admin_users")
        count = result[0] if result else 0
        
        if count == 0:
            # Создаем админа по умолчанию
            default_password = "admin123"
            password_hash = self.pwd_context.hash(default_password)
            
            query = """
                INSERT INTO admin_users (username, email, password_hash, role, is_active)
                VALUES ($1, $2, $3, $4, $5)
            """
            
            await adapter.execute(query, ("admin", "admin@localhost", password_hash, "super_admin", True))
            
            logger.warning(f"Создан админ пользователь по умолчанию: admin / {default_password}")
            logger.warning("ОБЯЗАТЕЛЬНО измените пароль после первого входа!")
        else:
            logger.info("Админ пользователи уже существуют")
    
    async def _assign_default_telegram_roles(self, adapter: DatabaseAdapter):
        """Назначить роли по умолчанию для Telegram пользователей"""
        logger.info("Назначение ролей Telegram пользователям...")
        user_roles = {
            5699315855: 'developer',      # Основной разработчик
            7610418399: 'senior_admin',   # Старший админ
            792247608: 'admin'            # Админ
        }
        
        for user_id, role in user_roles.items():
            # Проверяем, существует ли пользователь
            result = await adapter.fetch_one("SELECT user_id FROM users WHERE user_id = $1", (user_id,))
            
            if result:
                # Обновляем роль существующего пользователя
                await adapter.execute("UPDATE users SET role = $1 WHERE user_id = $2", (role, user_id))
                logger.info(f"Обновлена роль пользователя {user_id} на {role}")
            else:
                logger.info(f"Пользователь {user_id} будет создан с ролью {role} при первом обращении")


async def run_production_migrations(database_url: str):
    """Запустить production миграции"""
    migrations = ProductionMigrations(database_url)
    await migrations.run_critical_migrations()
    logger.info("✅ Все production миграции выполнены")


if __name__ == "__main__":
    import asyncio
    import os
    
    database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999!@findertool-hyvrte:5432/findertool_prod')
    asyncio.run(run_production_migrations(database_url))
