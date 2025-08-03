"""
Миграция 006: Исправление схемы таблицы broadcasts
Добавляет недостающую колонку scheduled_time и исправляет несоответствия
"""

from database.db_adapter import DatabaseAdapter

class Migration006:
    """Исправление схемы таблицы broadcasts"""
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        
        # Добавляем колонку scheduled_time в таблицу broadcasts
        try:
            await adapter.execute("""
                ALTER TABLE broadcasts 
                ADD COLUMN scheduled_time TIMESTAMP
            """)
            print("✅ Добавлена колонка scheduled_time в таблицу broadcasts")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("ℹ️ Колонка scheduled_time уже существует")
            else:
                print(f"⚠️ Ошибка при добавлении scheduled_time: {e}")
        
        # Добавляем недостающие колонки если их нет
        columns_to_add = [
            ("title", "VARCHAR(255)"),
            ("status", "VARCHAR(50) DEFAULT 'pending'"),
            ("parse_mode", "VARCHAR(50) DEFAULT 'HTML'"),
            ("target_users", "VARCHAR(100) DEFAULT 'all'"),
            ("created_by", "INTEGER"),
            ("started_at", "TIMESTAMP"),
            ("completed_at", "TIMESTAMP"),
            ("error_message", "TEXT")
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                await adapter.execute(f"""
                    ALTER TABLE broadcasts 
                    ADD COLUMN {column_name} {column_type}
                """)
                print(f"✅ Добавлена колонка {column_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"ℹ️ Колонка {column_name} уже существует")
                else:
                    print(f"⚠️ Ошибка при добавлении {column_name}: {e}")
        
        # Создаем индексы для производительности
        indexes = [
            ("idx_broadcasts_status", "broadcasts", "status"),
            ("idx_broadcasts_created_by", "broadcasts", "created_by"),
            ("idx_broadcasts_scheduled_time", "broadcasts", "scheduled_time"),
            ("idx_broadcasts_target_users", "broadcasts", "target_users")
        ]
        
        for index_name, table_name, column_name in indexes:
            try:
                await adapter.execute(f"""
                    CREATE INDEX IF NOT EXISTS {index_name} 
                    ON {table_name} ({column_name})
                """)
                print(f"✅ Создан индекс {index_name}")
            except Exception as e:
                print(f"⚠️ Ошибка при создании индекса {index_name}: {e}")
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        
        # Удаляем индексы
        indexes = [
            "idx_broadcasts_status",
            "idx_broadcasts_created_by", 
            "idx_broadcasts_scheduled_time",
            "idx_broadcasts_target_users"
        ]
        
        for index_name in indexes:
            try:
                await adapter.execute(f"DROP INDEX IF EXISTS {index_name}")
                print(f"✅ Удален индекс {index_name}")
            except Exception as e:
                print(f"⚠️ Ошибка при удалении индекса {index_name}: {e}")
        
        # Удаляем добавленные колонки
        columns_to_remove = [
            "scheduled_time", "title", "status", "parse_mode", 
            "target_users", "created_by", "started_at", 
            "completed_at", "error_message"
        ]
        
        for column_name in columns_to_remove:
            try:
                await adapter.execute(f"ALTER TABLE broadcasts DROP COLUMN {column_name}")
                print(f"✅ Удалена колонка {column_name}")
            except Exception as e:
                print(f"⚠️ Ошибка при удалении колонки {column_name}: {e}")

# Экспортируем класс для менеджера миграций
Migration = Migration006
