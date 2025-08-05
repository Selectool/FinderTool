"""
Миграция 007: Добавление поддержки медиафайлов в рассылки
"""

from database.db_adapter import DatabaseAdapter


class Migration007:
    """Добавление поддержки медиафайлов в таблицу broadcasts"""

    description = "Добавление поддержки медиафайлов в рассылки - колонки message_type, media_file, media_type, media_caption"
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        print("🔄 Применение миграции 007: Добавление поддержки медиафайлов...")
        
        # Добавляем колонки для медиафайлов в таблицу broadcasts
        media_columns = [
            ("message_type", "VARCHAR(50) DEFAULT 'text'"),
            ("media_file", "TEXT"),
            ("media_type", "VARCHAR(50)"),
            ("media_caption", "TEXT")
        ]
        
        for column_name, column_type in media_columns:
            try:
                if adapter.db_type == 'sqlite':
                    query = f"ALTER TABLE broadcasts ADD COLUMN {column_name} {column_type.replace('VARCHAR', 'TEXT')}"
                else:  # PostgreSQL
                    query = f"ALTER TABLE broadcasts ADD COLUMN {column_name} {column_type}"
                
                await adapter.execute(query)
                print(f"✅ Добавлена колонка {column_name} в таблицу broadcasts")
                
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print(f"ℹ️ Колонка {column_name} уже существует в таблице broadcasts")
                else:
                    print(f"⚠️ Ошибка при добавлении колонки {column_name}: {e}")
        
        # Также добавляем поддержку медиафайлов в scheduled_broadcasts если таблица существует
        try:
            # Проверяем существование таблицы scheduled_broadcasts
            if adapter.db_type == 'sqlite':
                check_query = "SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_broadcasts'"
            else:  # PostgreSQL
                check_query = "SELECT table_name FROM information_schema.tables WHERE table_name='scheduled_broadcasts'"
            
            result = await adapter.fetch_one(check_query)
            
            if result:
                print("🔄 Добавляем поддержку медиафайлов в scheduled_broadcasts...")
                
                for column_name, column_type in media_columns:
                    try:
                        if adapter.db_type == 'sqlite':
                            query = f"ALTER TABLE scheduled_broadcasts ADD COLUMN {column_name} {column_type.replace('VARCHAR', 'TEXT')}"
                        else:  # PostgreSQL
                            query = f"ALTER TABLE scheduled_broadcasts ADD COLUMN {column_name} {column_type}"
                        
                        await adapter.execute(query)
                        print(f"✅ Добавлена колонка {column_name} в таблицу scheduled_broadcasts")
                        
                    except Exception as e:
                        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                            print(f"ℹ️ Колонка {column_name} уже существует в таблице scheduled_broadcasts")
                        else:
                            print(f"⚠️ Ошибка при добавлении колонки {column_name} в scheduled_broadcasts: {e}")
            else:
                print("ℹ️ Таблица scheduled_broadcasts не найдена, пропускаем")
                
        except Exception as e:
            print(f"⚠️ Ошибка при проверке таблицы scheduled_broadcasts: {e}")
        
        print("✅ Миграция 007 завершена: Поддержка медиафайлов добавлена")
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        print("🔄 Откат миграции 007: Удаление поддержки медиафайлов...")
        
        # В SQLite нельзя удалять колонки, поэтому просто логируем
        if adapter.db_type == 'sqlite':
            print("⚠️ SQLite не поддерживает удаление колонок. Откат невозможен.")
            return
        
        # Для PostgreSQL удаляем колонки
        media_columns = ["message_type", "media_file", "media_type", "media_caption"]
        
        for column_name in media_columns:
            try:
                await adapter.execute(f"ALTER TABLE broadcasts DROP COLUMN IF EXISTS {column_name}")
                print(f"✅ Удалена колонка {column_name} из таблицы broadcasts")
            except Exception as e:
                print(f"⚠️ Ошибка при удалении колонки {column_name}: {e}")
        
        # Также удаляем из scheduled_broadcasts
        try:
            for column_name in media_columns:
                try:
                    await adapter.execute(f"ALTER TABLE scheduled_broadcasts DROP COLUMN IF EXISTS {column_name}")
                    print(f"✅ Удалена колонка {column_name} из таблицы scheduled_broadcasts")
                except Exception as e:
                    print(f"⚠️ Ошибка при удалении колонки {column_name} из scheduled_broadcasts: {e}")
        except Exception as e:
            print(f"⚠️ Ошибка при работе с таблицей scheduled_broadcasts: {e}")
        
        print("✅ Откат миграции 007 завершен")


# Экспорт для системы миграций
Migration = Migration007
