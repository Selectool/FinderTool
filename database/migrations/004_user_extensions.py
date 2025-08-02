"""
Миграция 004: Расширение таблицы пользователей
Создана: 2025-08-02 22:30:00
"""
from database.migration_manager import Migration
from database.db_adapter import DatabaseAdapter

class Migration004(Migration):
    def __init__(self):
        super().__init__("004", "Расширение таблицы пользователей (роли, блокировки, заметки)")
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        # Добавляем новые колонки в таблицу users
        columns_to_add = [
            ("role", "TEXT DEFAULT 'user'" if adapter.db_type == 'sqlite' else "VARCHAR(100) DEFAULT 'user'"),
            ("unlimited_access", "BOOLEAN DEFAULT FALSE"),
            ("notes", "TEXT"),
            ("blocked", "BOOLEAN DEFAULT FALSE"),
            ("bot_blocked", "BOOLEAN DEFAULT FALSE"),
            ("blocked_at", "TIMESTAMP"),
            ("blocked_by", "INTEGER"),
            ("referrer_id", "INTEGER"),
            ("registration_source", "TEXT DEFAULT 'bot'" if adapter.db_type == 'sqlite' else "VARCHAR(100) DEFAULT 'bot'")
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                await adapter.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
            except Exception as e:
                # Игнорируем ошибки если колонка уже существует
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    continue
                else:
                    # Логируем другие ошибки, но не прерываем миграцию
                    print(f"Предупреждение при добавлении колонки {column_name}: {e}")
        
        # Назначаем роли специальным пользователям
        user_roles = {
            5699315855: 'developer',      # Основной разработчик
            7610418399: 'senior_admin',   # Старший админ
            792247608: 'admin'            # Админ
        }
        
        for user_id, role in user_roles.items():
            if adapter.db_type == 'sqlite':
                update_query = "UPDATE users SET role = ? WHERE user_id = ?"
            else:  # PostgreSQL
                update_query = "UPDATE users SET role = $1 WHERE user_id = $2"
            
            try:
                await adapter.execute(update_query, (role, user_id))
            except Exception as e:
                # Пользователь может не существовать, это нормально
                print(f"Пользователь {user_id} не найден для назначения роли {role}")
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        # Удаляем добавленные колонки
        columns_to_remove = [
            "role", "unlimited_access", "notes", "blocked", "bot_blocked",
            "blocked_at", "blocked_by", "referrer_id", "registration_source"
        ]
        
        for column_name in columns_to_remove:
            try:
                await adapter.execute(f"ALTER TABLE users DROP COLUMN {column_name}")
            except Exception as e:
                # Игнорируем ошибки если колонка не существует
                print(f"Предупреждение при удалении колонки {column_name}: {e}")

# Экспортируем класс для менеджера миграций
Migration = Migration004
