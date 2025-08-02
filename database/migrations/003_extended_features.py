"""
Миграция 003: Расширенные функции
Создана: 2025-08-02 22:30:00
"""
from database.migration_manager import Migration
from database.db_adapter import DatabaseAdapter

class Migration003(Migration):
    def __init__(self):
        super().__init__("003", "Расширенные функции (шаблоны, планировщик, логи)")
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        # Таблица шаблонов сообщений
        if adapter.db_type == 'sqlite':
            templates_query = """
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
            templates_query = """
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
        
        await adapter.execute(templates_query)
        
        # Таблица планировщика рассылок
        if adapter.db_type == 'sqlite':
            scheduled_query = """
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
            scheduled_query = """
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
        
        await adapter.execute(scheduled_query)
        
        # Таблица логов действий
        if adapter.db_type == 'sqlite':
            audit_query = """
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
            audit_query = """
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
        
        await adapter.execute(audit_query)
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        await adapter.execute("DROP TABLE IF EXISTS audit_logs")
        await adapter.execute("DROP TABLE IF EXISTS scheduled_broadcasts")
        await adapter.execute("DROP TABLE IF EXISTS message_templates")

# Экспортируем класс для менеджера миграций
Migration = Migration003
