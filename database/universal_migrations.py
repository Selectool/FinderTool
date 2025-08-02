"""
Универсальные миграции для SQLite и PostgreSQL
Обеспечивает полную синхронизацию схемы между локальной и production базой
"""
import logging
from datetime import datetime
from database.db_adapter import DatabaseAdapter
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

class UniversalMigrations:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    async def run_all_migrations(self):
        """Выполнить все миграции для обеспечения полной схемы"""
        logger.info("🚀 Запуск универсальных миграций...")
        
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            # Создаем таблицу миграций
            await self._create_migrations_table(adapter)
            
            # Список всех миграций
            migrations = [
                ('create_admin_users_table', self._create_admin_users_table),
                ('create_roles_table', self._create_roles_table),
                ('create_message_templates_table', self._create_message_templates_table),
                ('create_scheduled_broadcasts_table', self._create_scheduled_broadcasts_table),
                ('create_audit_logs_table', self._create_audit_logs_table),
                ('create_ab_tests_table', self._create_ab_tests_table),
                ('create_broadcast_logs_table', self._create_broadcast_logs_table),
                ('create_user_permissions_table', self._create_user_permissions_table),
                ('extend_users_table', self._extend_users_table),
                ('extend_broadcasts_table', self._extend_broadcasts_table),
                ('add_status_to_broadcasts', self._add_status_to_broadcasts),
                ('add_title_to_broadcasts', self._add_title_to_broadcasts),
                ('insert_default_roles', self._insert_default_roles),
                ('create_default_admin_user', self._create_default_admin_user),
                ('add_telegram_user_roles', self._add_telegram_user_roles),
                ('assign_default_telegram_roles', self._assign_default_telegram_roles)
            ]
            
            migrations_executed = 0
            
            for migration_name, migration_func in migrations:
                # Проверяем, выполнена ли миграция
                if adapter.db_type == 'sqlite':
                    check_query = "SELECT COUNT(*) FROM schema_migrations WHERE migration_name = ?"
                else:  # PostgreSQL
                    check_query = "SELECT COUNT(*) FROM schema_migrations WHERE migration_name = $1"
                
                result = await adapter.fetch_one(check_query, (migration_name,))
                
                if result and result[0] == 0:
                    logger.info(f"Выполняем миграцию: {migration_name}")
                    await migration_func(adapter)
                    
                    # Записываем выполненную миграцию
                    if adapter.db_type == 'sqlite':
                        insert_query = "INSERT INTO schema_migrations (migration_name) VALUES (?)"
                    else:  # PostgreSQL
                        insert_query = "INSERT INTO schema_migrations (migration_name) VALUES ($1)"
                    
                    await adapter.execute(insert_query, (migration_name,))
                    migrations_executed += 1
                    logger.info(f"✅ Миграция {migration_name} выполнена")
                else:
                    logger.debug(f"Миграция {migration_name} уже выполнена")
            
            if migrations_executed == 0:
                logger.info("✅ Все миграции уже выполнены")
            else:
                logger.info(f"✅ Выполнено {migrations_executed} новых миграций")
                
        finally:
            await adapter.disconnect()
    
    async def _create_migrations_table(self, adapter: DatabaseAdapter):
        """Создать таблицу для отслеживания миграций"""
        if adapter.db_type == 'sqlite':
            query = """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_name TEXT UNIQUE NOT NULL,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        else:  # PostgreSQL
            query = """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id SERIAL PRIMARY KEY,
                    migration_name VARCHAR(255) UNIQUE NOT NULL,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        await adapter.execute(query)
    
    async def _create_admin_users_table(self, adapter: DatabaseAdapter):
        """Создать таблицу админ пользователей"""
        if adapter.db_type == 'sqlite':
            query = """
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'moderator',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    created_by INTEGER,
                    FOREIGN KEY (created_by) REFERENCES admin_users (id)
                )
            """
        else:  # PostgreSQL
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
    
    async def _create_roles_table(self, adapter: DatabaseAdapter):
        """Создать таблицу ролей"""
        if adapter.db_type == 'sqlite':
            query = """
                CREATE TABLE IF NOT EXISTS roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    permissions TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        else:  # PostgreSQL
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
    
    async def _create_message_templates_table(self, adapter: DatabaseAdapter):
        """Создать таблицу шаблонов сообщений"""
        if adapter.db_type == 'sqlite':
            query = """
                CREATE TABLE IF NOT EXISTS message_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    parse_mode TEXT DEFAULT 'HTML',
                    category TEXT DEFAULT 'general',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES admin_users (id)
                )
            """
        else:  # PostgreSQL
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
    
    async def _create_scheduled_broadcasts_table(self, adapter: DatabaseAdapter):
        """Создать таблицу планировщика рассылок"""
        if adapter.db_type == 'sqlite':
            query = """
                CREATE TABLE IF NOT EXISTS scheduled_broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    template_id INTEGER,
                    message_text TEXT,
                    parse_mode TEXT DEFAULT 'HTML',
                    scheduled_at TIMESTAMP NOT NULL,
                    status TEXT DEFAULT 'pending',
                    target_users TEXT DEFAULT 'all',
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
        else:  # PostgreSQL
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
    
    async def _create_audit_logs_table(self, adapter: DatabaseAdapter):
        """Создать таблицу логов действий"""
        if adapter.db_type == 'sqlite':
            query = """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_user_id INTEGER,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id INTEGER,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_user_id) REFERENCES admin_users (id)
                )
            """
        else:  # PostgreSQL
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
    
    async def _create_ab_tests_table(self, adapter: DatabaseAdapter):
        """Создать таблицу A/B тестов"""
        if adapter.db_type == 'sqlite':
            query = """
                CREATE TABLE IF NOT EXISTS ab_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    variant_a_content TEXT NOT NULL,
                    variant_b_content TEXT NOT NULL,
                    target_users TEXT DEFAULT 'all',
                    status TEXT DEFAULT 'draft',
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
        else:  # PostgreSQL
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
