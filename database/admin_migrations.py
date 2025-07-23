"""
Миграции для админ-панели
"""
import aiosqlite
import logging
from typing import List

logger = logging.getLogger(__name__)


class AdminMigrations:
    """Класс для выполнения миграций админ-панели"""
    
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
    
    async def run_migrations(self):
        """Выполнить все миграции"""
        migrations = [
            self._create_admin_users_table,
            self._create_roles_table,
            self._create_message_templates_table,
            self._create_scheduled_broadcasts_table,
            self._create_audit_logs_table,
            self._create_ab_tests_table,
            self._extend_users_table,
            self._extend_broadcasts_table,
            self._insert_default_roles,
            self._create_default_admin_user
        ]
        
        async with aiosqlite.connect(self.db_path) as db:
            for migration in migrations:
                try:
                    await migration(db)
                    logger.info(f"Миграция {migration.__name__} выполнена успешно")
                except Exception as e:
                    logger.error(f"Ошибка выполнения миграции {migration.__name__}: {e}")
                    # Продолжаем выполнение других миграций
            
            await db.commit()
    
    async def _create_admin_users_table(self, db: aiosqlite.Connection):
        """Создать таблицу админ пользователей"""
        await db.execute("""
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
        """)
    
    async def _create_roles_table(self, db: aiosqlite.Connection):
        """Создать таблицу ролей"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                permissions TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    async def _create_message_templates_table(self, db: aiosqlite.Connection):
        """Создать таблицу шаблонов сообщений"""
        await db.execute("""
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
        """)
    
    async def _create_scheduled_broadcasts_table(self, db: aiosqlite.Connection):
        """Создать таблицу планировщика рассылок"""
        await db.execute("""
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
        """)
    
    async def _create_audit_logs_table(self, db: aiosqlite.Connection):
        """Создать таблицу логов действий"""
        await db.execute("""
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
        """)
    
    async def _create_ab_tests_table(self, db: aiosqlite.Connection):
        """Создать таблицу A/B тестов"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ab_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                variant_a_template_id INTEGER,
                variant_b_template_id INTEGER,
                split_ratio REAL DEFAULT 0.5,
                status TEXT DEFAULT 'draft',
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                variant_a_sent INTEGER DEFAULT 0,
                variant_b_sent INTEGER DEFAULT 0,
                variant_a_success INTEGER DEFAULT 0,
                variant_b_success INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (variant_a_template_id) REFERENCES message_templates (id),
                FOREIGN KEY (variant_b_template_id) REFERENCES message_templates (id),
                FOREIGN KEY (created_by) REFERENCES admin_users (id)
            )
        """)
    
    async def _extend_users_table(self, db: aiosqlite.Connection):
        """Расширить таблицу пользователей"""
        # Проверяем существование колонок перед добавлением
        columns_to_add = [
            ("role", "TEXT DEFAULT 'user'"),
            ("unlimited_access", "BOOLEAN DEFAULT FALSE"),
            ("notes", "TEXT"),
            ("blocked", "BOOLEAN DEFAULT FALSE"),
            ("bot_blocked", "BOOLEAN DEFAULT FALSE"),
            ("blocked_at", "TIMESTAMP"),
            ("blocked_by", "INTEGER"),
            ("referrer_id", "INTEGER"),
            ("registration_source", "TEXT DEFAULT 'bot'")
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
            except aiosqlite.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise e
    
    async def _extend_broadcasts_table(self, db: aiosqlite.Connection):
        """Расширить таблицу рассылок"""
        columns_to_add = [
            ("template_id", "INTEGER"),
            ("parse_mode", "TEXT DEFAULT 'HTML'"),
            ("target_users", "TEXT DEFAULT 'all'"),
            ("created_by", "INTEGER"),
            ("ab_test_id", "INTEGER"),
            ("scheduled_at", "TIMESTAMP"),
            ("started_at", "TIMESTAMP"),
            ("error_message", "TEXT")
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                await db.execute(f"ALTER TABLE broadcasts ADD COLUMN {column_name} {column_def}")
            except aiosqlite.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise e
    
    async def _insert_default_roles(self, db: aiosqlite.Connection):
        """Вставить роли по умолчанию"""
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
            await db.execute("""
                INSERT OR IGNORE INTO roles (name, display_name, permissions, description)
                VALUES (?, ?, ?, ?)
            """, (role['name'], role['display_name'], role['permissions'], role['description']))
    
    async def _create_default_admin_user(self, db: aiosqlite.Connection):
        """Создать пользователя админа по умолчанию"""
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Проверяем, есть ли уже админ пользователи
        cursor = await db.execute("SELECT COUNT(*) FROM admin_users")
        count = (await cursor.fetchone())[0]
        
        if count == 0:
            # Создаем админа по умолчанию
            default_password = "admin123"  # В production должен быть изменен
            password_hash = pwd_context.hash(default_password)
            
            await db.execute("""
                INSERT INTO admin_users (username, email, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, ("admin", "admin@localhost", password_hash, "super_admin", True))
            
            logger.warning(f"Создан админ пользователь по умолчанию: admin / {default_password}")
            logger.warning("ОБЯЗАТЕЛЬНО измените пароль после первого входа!")


async def run_admin_migrations(db_path: str = "bot.db"):
    """Запустить миграции админ-панели"""
    migrations = AdminMigrations(db_path)
    await migrations.run_migrations()
    logger.info("Все миграции админ-панели выполнены")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_admin_migrations())
