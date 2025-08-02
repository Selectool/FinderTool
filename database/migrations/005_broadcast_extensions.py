"""
Миграция 005: Расширение таблицы рассылок
Создана: 2025-08-02 22:30:00
"""
from database.migration_manager import Migration
from database.db_adapter import DatabaseAdapter

class Migration005(Migration):
    def __init__(self):
        super().__init__("005", "Расширение таблицы рассылок и добавление логов")
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        # Добавляем новые колонки в таблицу broadcast_messages
        columns_to_add = [
            ("title", "TEXT" if adapter.db_type == 'sqlite' else "VARCHAR(255)"),
            ("status", "TEXT DEFAULT 'pending'" if adapter.db_type == 'sqlite' else "VARCHAR(50) DEFAULT 'pending'"),
            ("template_id", "INTEGER"),
            ("parse_mode", "TEXT DEFAULT 'HTML'" if adapter.db_type == 'sqlite' else "VARCHAR(50) DEFAULT 'HTML'"),
            ("target_users", "TEXT DEFAULT 'all'" if adapter.db_type == 'sqlite' else "VARCHAR(100) DEFAULT 'all'"),
            ("created_by", "INTEGER"),
            ("ab_test_id", "INTEGER"),
            ("scheduled_at", "TIMESTAMP"),
            ("started_at", "TIMESTAMP"),
            ("error_message", "TEXT")
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                await adapter.execute(f"ALTER TABLE broadcast_messages ADD COLUMN {column_name} {column_def}")
            except Exception as e:
                # Игнорируем ошибки если колонка уже существует
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    continue
                else:
                    print(f"Предупреждение при добавлении колонки {column_name}: {e}")
        
        # Создаем таблицу логов рассылок
        if adapter.db_type == 'sqlite':
            logs_query = """
                CREATE TABLE IF NOT EXISTS broadcast_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broadcast_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    error_details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (broadcast_id) REFERENCES broadcast_messages (id)
                )
            """
        else:  # PostgreSQL
            logs_query = """
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
        
        await adapter.execute(logs_query)
        
        # Создаем индексы для производительности
        await adapter.execute("""
            CREATE INDEX IF NOT EXISTS idx_broadcast_logs_broadcast_id
            ON broadcast_logs (broadcast_id)
        """)
        
        await adapter.execute("""
            CREATE INDEX IF NOT EXISTS idx_broadcast_logs_status
            ON broadcast_logs (broadcast_id, status)
        """)
        
        # Создаем таблицу A/B тестов
        if adapter.db_type == 'sqlite':
            ab_tests_query = """
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
            ab_tests_query = """
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
        
        await adapter.execute(ab_tests_query)
        
        # Создаем таблицу прав доступа пользователей
        if adapter.db_type == 'sqlite':
            permissions_query = """
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    permission TEXT NOT NULL,
                    granted_by INTEGER,
                    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES admin_users (id),
                    FOREIGN KEY (granted_by) REFERENCES admin_users (id),
                    UNIQUE(user_id, permission)
                )
            """
        else:  # PostgreSQL
            permissions_query = """
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
        
        await adapter.execute(permissions_query)
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        await adapter.execute("DROP TABLE IF EXISTS user_permissions")
        await adapter.execute("DROP TABLE IF EXISTS ab_tests")
        await adapter.execute("DROP TABLE IF EXISTS broadcast_logs")
        
        # Удаляем добавленные колонки
        columns_to_remove = [
            "title", "status", "template_id", "parse_mode", "target_users",
            "created_by", "ab_test_id", "scheduled_at", "started_at", "error_message"
        ]
        
        for column_name in columns_to_remove:
            try:
                await adapter.execute(f"ALTER TABLE broadcast_messages DROP COLUMN {column_name}")
            except Exception as e:
                print(f"Предупреждение при удалении колонки {column_name}: {e}")

# Экспортируем класс для менеджера миграций
Migration = Migration005
