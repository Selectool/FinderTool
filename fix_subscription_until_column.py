#!/usr/bin/env python3
"""
Исправление проблемы с колонкой subscription_until в таблице users
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


async def fix_subscription_until_column():
    """Исправляет проблему с колонкой subscription_until"""
    
    print("🔧 Исправление колонки subscription_until в таблице users")
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
        
        print("\n📊 Этап 1: Проверка текущей структуры таблицы users...")
        
        # Проверяем структуру таблицы users
        if db_type == 'postgresql':
            columns_query = """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'users'
                ORDER BY ordinal_position
            """
        else:
            columns_query = "PRAGMA table_info(users)"
        
        columns = await adapter.fetch_all(columns_query)
        
        if not columns:
            print("❌ Таблица users не найдена!")
            return False
        
        # Проверяем наличие нужных колонок
        column_names = [col[0] if isinstance(col, tuple) else col.get('column_name', col.get('name', '')) for col in columns]
        
        has_subscription_until = 'subscription_until' in column_names
        has_subscription_end = 'subscription_end' in column_names
        
        print(f"   - subscription_until: {'✅' if has_subscription_until else '❌'}")
        print(f"   - subscription_end: {'✅' if has_subscription_end else '❌'}")
        
        if has_subscription_until:
            print("✅ Колонка subscription_until уже существует")
            return True
        
        print("\n🔧 Этап 2: Добавление колонки subscription_until...")
        
        # Добавляем колонку subscription_until
        if db_type == 'postgresql':
            add_column_query = """
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS subscription_until TIMESTAMP
            """
        else:
            add_column_query = """
                ALTER TABLE users 
                ADD COLUMN subscription_until TIMESTAMP
            """
        
        try:
            await adapter.execute(add_column_query)
            print("✅ Колонка subscription_until добавлена")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("✅ Колонка subscription_until уже существует")
            else:
                print(f"❌ Ошибка добавления колонки: {e}")
                return False
        
        print("\n🔄 Этап 3: Синхронизация данных...")
        
        if has_subscription_end:
            # Синхронизируем subscription_until с subscription_end
            sync_query = """
                UPDATE users 
                SET subscription_until = subscription_end 
                WHERE subscription_until IS NULL AND subscription_end IS NOT NULL
            """
            
            try:
                await adapter.execute(sync_query)
                print("✅ Данные синхронизированы с subscription_end")
            except Exception as e:
                print(f"⚠️ Не удалось синхронизировать данные: {e}")
        
        print("\n📊 Этап 4: Создание индекса...")
        
        # Создаем индекс для оптимизации
        index_query = """
            CREATE INDEX IF NOT EXISTS idx_users_subscription_until 
            ON users(subscription_until)
        """
        
        try:
            await adapter.execute(index_query)
            print("✅ Индекс создан")
        except Exception as e:
            print(f"⚠️ Не удалось создать индекс: {e}")
        
        print("\n📊 Этап 5: Финальная проверка...")
        
        # Проверяем результат
        check_query = """
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN subscription_until IS NOT NULL THEN 1 END) as with_subscription,
                COUNT(CASE WHEN subscription_until IS NULL THEN 1 END) as null_values
            FROM users
        """
        
        result = await adapter.fetch_one(check_query)
        if result:
            total, with_sub, nulls = result
            print(f"📈 Статистика пользователей:")
            print(f"   - Всего: {total}")
            print(f"   - С subscription_until: {with_sub}")
            print(f"   - NULL значений: {nulls}")
        
        print("\n✅ Исправление колонки subscription_until завершено успешно!")
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
    success = await fix_subscription_until_column()
    
    if success:
        print("\n🔄 Рекомендуется перезапустить сервисы для применения изменений")
        return True
    else:
        print("\n❌ Исправление не удалось")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
