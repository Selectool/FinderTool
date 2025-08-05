#!/usr/bin/env python3
"""
Исправление проблемы с колонкой message в таблице broadcasts
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from database.db_adapter import DatabaseAdapter

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fix_broadcasts_message_column():
    """Исправляет проблему с колонкой message в таблице broadcasts"""
    
    print("🔧 Исправление колонки message в таблице broadcasts")
    print("=" * 60)
    
    # Получаем URL базы данных
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        database_url = 'postgresql://findertool_user:Findertool1999!@localhost:5432/findertool_prod'
        print(f"⚠️ DATABASE_URL не установлен, используем: {database_url}")
    else:
        print(f"🔗 Используется БД: {database_url}")
    
    db_type = 'postgresql' if database_url.startswith('postgresql') else 'sqlite'
    
    try:
        adapter = DatabaseAdapter(database_url)
        await adapter.connect()
        
        print("\n📊 Этап 1: Проверка текущей структуры таблицы broadcasts...")
        
        # Проверяем структуру таблицы broadcasts
        if db_type == 'postgresql':
            columns_query = """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'broadcasts'
                ORDER BY ordinal_position
            """
        else:
            columns_query = "PRAGMA table_info(broadcasts)"
        
        columns = await adapter.fetch_all(columns_query)
        
        if not columns:
            print("❌ Таблица broadcasts не найдена!")
            return False
        
        # Ищем колонку message
        message_column = None
        for col in columns:
            if isinstance(col, dict):
                col_name = col.get('column_name', '')
                is_nullable = col.get('is_nullable', 'YES')
            else:
                col_name = col[0] if isinstance(col, tuple) else str(col)
                is_nullable = 'YES'  # Для SQLite по умолчанию
            
            if col_name == 'message':
                message_column = {
                    'name': col_name,
                    'nullable': is_nullable == 'YES'
                }
                break
        
        if not message_column:
            print("❌ Колонка message не найдена в таблице broadcasts!")
            return False
        
        print(f"   - Колонка message: {'✅ nullable' if message_column['nullable'] else '❌ NOT NULL'}")
        
        if message_column['nullable']:
            print("✅ Колонка message уже допускает NULL значения")
        else:
            print("\n🔧 Этап 2: Делаем колонку message nullable...")
            
            # Делаем колонку nullable
            if db_type == 'postgresql':
                alter_query = "ALTER TABLE broadcasts ALTER COLUMN message DROP NOT NULL"
            else:
                # Для SQLite нужно пересоздать таблицу
                print("⚠️ SQLite требует пересоздания таблицы для изменения NOT NULL")
                return False
            
            try:
                await adapter.execute(alter_query)
                print("✅ Колонка message теперь допускает NULL значения")
            except Exception as e:
                print(f"❌ Ошибка изменения колонки: {e}")
                return False
        
        print("\n🔄 Этап 3: Обновление существующих записей с NULL...")
        
        # Обновляем записи с NULL значениями
        update_query = """
            UPDATE broadcasts 
            SET message = COALESCE(message_text, title, 'Сообщение не указано')
            WHERE message IS NULL
        """
        
        try:
            result = await adapter.execute(update_query)
            print("✅ Обновлены записи с NULL значениями")
        except Exception as e:
            print(f"⚠️ Не удалось обновить записи: {e}")
        
        print("\n🔧 Этап 4: Установка значения по умолчанию...")
        
        # Устанавливаем значение по умолчанию
        if db_type == 'postgresql':
            default_query = "ALTER TABLE broadcasts ALTER COLUMN message SET DEFAULT ''"
        else:
            print("⚠️ SQLite не поддерживает изменение DEFAULT для существующих колонок")
            default_query = None
        
        if default_query:
            try:
                await adapter.execute(default_query)
                print("✅ Установлено значение по умолчанию для колонки message")
            except Exception as e:
                print(f"⚠️ Не удалось установить значение по умолчанию: {e}")
        
        print("\n📊 Этап 5: Финальная проверка...")
        
        # Проверяем результат
        check_query = """
            SELECT 
                COUNT(*) as total_broadcasts,
                COUNT(CASE WHEN message IS NULL THEN 1 END) as null_messages,
                COUNT(CASE WHEN message = '' THEN 1 END) as empty_messages
            FROM broadcasts
        """
        
        result = await adapter.fetch_one(check_query)
        if result:
            total, nulls, empty = result
            print(f"📈 Статистика рассылок:")
            print(f"   - Всего: {total}")
            print(f"   - С NULL message: {nulls}")
            print(f"   - С пустым message: {empty}")
        
        print("\n✅ Исправление колонки message завершено успешно!")
        return True
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        try:
            await adapter.disconnect()
        except:
            pass


async def main():
    """Основная функция"""
    success = await fix_broadcasts_message_column()
    
    if success:
        print("\n🔄 Рекомендуется перезапустить админ-панель для применения изменений")
        return True
    else:
        print("\n❌ Исправление не удалось")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
