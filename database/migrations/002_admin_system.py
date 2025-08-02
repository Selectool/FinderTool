"""
Миграция 002: Система администрирования
Создана: 2025-08-02 22:30:00
"""
from database.migration_manager import Migration
from database.db_adapter import DatabaseAdapter
from passlib.context import CryptContext

class Migration002(Migration):
    def __init__(self):
        super().__init__("002", "Создание системы администрирования (admin_users, roles)")
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        # Таблица админ пользователей
        if adapter.db_type == 'sqlite':
            admin_users_query = """
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
            admin_users_query = """
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
        
        await adapter.execute(admin_users_query)
        
        # Таблица ролей
        if adapter.db_type == 'sqlite':
            roles_query = """
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
            roles_query = """
                CREATE TABLE IF NOT EXISTS roles (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    display_name VARCHAR(255) NOT NULL,
                    permissions TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        
        await adapter.execute(roles_query)
        
        # Вставляем роли по умолчанию
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
            if adapter.db_type == 'sqlite':
                query = """
                    INSERT OR IGNORE INTO roles (name, display_name, permissions, description)
                    VALUES (?, ?, ?, ?)
                """
            else:  # PostgreSQL
                query = """
                    INSERT INTO roles (name, display_name, permissions, description)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (name) DO NOTHING
                """
            
            await adapter.execute(query, (role['name'], role['display_name'], role['permissions'], role['description']))
        
        # Создаем админ пользователя по умолчанию
        default_password = "admin123"
        password_hash = self.pwd_context.hash(default_password)
        
        if adapter.db_type == 'sqlite':
            admin_query = """
                INSERT OR IGNORE INTO admin_users (username, email, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
            """
        else:  # PostgreSQL
            admin_query = """
                INSERT INTO admin_users (username, email, password_hash, role, is_active)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (username) DO NOTHING
            """
        
        await adapter.execute(admin_query, ("admin", "admin@localhost", password_hash, "super_admin", True))
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        await adapter.execute("DROP TABLE IF EXISTS admin_users")
        await adapter.execute("DROP TABLE IF EXISTS roles")

# Экспортируем класс для менеджера миграций
Migration = Migration002
