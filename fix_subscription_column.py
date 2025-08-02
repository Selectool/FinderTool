#!/usr/bin/env python3
"""
Исправление проблемы с колонкой is_subscribed в таблице users
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


async def fix_subscription_column():
    """Исправляет проблему с колонкой is_subscribed"""
    
    print("🔧 Исправление колонки is_subscribed в таблице users")
    print("=" * 55)
    
    # Получаем URL базы данных
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        database_url = 'postgresql://findertool_user:Findertool1999@localhost:5432/findertool_prod'
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
        
        print("📋 Текущие колонки в таблице users:")
        column_names = []
        for col in columns:
            if db_type == 'postgresql':
                column_names.append(col[0])
                print(f"   - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
            else:
                column_names.append(col[1])
                print(f"   - {col[1]} ({col[2]}) {'NULL' if col[3] == 0 else 'NOT NULL'}")
        
        # Проверяем наличие нужных колонок
        has_is_subscribed = 'is_subscribed' in column_names
        has_subscription_active = 'subscription_active' in column_names
        
        print(f"\n🔍 Анализ колонок:")
        print(f"   - is_subscribed: {'✅ есть' if has_is_subscribed else '❌ нет'}")
        print(f"   - subscription_active: {'✅ есть' if has_subscription_active else '❌ нет'}")
        
        if has_is_subscribed:
            print("✅ Колонка is_subscribed уже существует")
            
            # Проверяем синхронизацию данных
            if has_subscription_active:
                print("\n🔄 Проверяем синхронизацию данных...")
                
                sync_query = """
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN is_subscribed != subscription_active THEN 1 END) as mismatched
                    FROM users 
                    WHERE is_subscribed IS NOT NULL AND subscription_active IS NOT NULL
                """
                
                result = await adapter.fetch_one(sync_query)
                if result:
                    total, mismatched = result
                    print(f"   - Всего записей: {total}")
                    print(f"   - Несинхронизированных: {mismatched}")
                    
                    if mismatched > 0:
                        print("🔄 Синхронизируем данные...")
                        sync_update = """
                            UPDATE users 
                            SET is_subscribed = subscription_active 
                            WHERE is_subscribed != subscription_active
                        """
                        await adapter.execute(sync_update)
                        print("✅ Данные синхронизированы")
            
            return True
        
        print("\n🔧 Этап 2: Добавление колонки is_subscribed...")
        
        # Добавляем колонку is_subscribed
        if db_type == 'postgresql':
            add_column_query = """
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS is_subscribed BOOLEAN DEFAULT FALSE
            """
        else:
            add_column_query = """
                ALTER TABLE users 
                ADD COLUMN is_subscribed BOOLEAN DEFAULT FALSE
            """
        
        try:
            await adapter.execute(add_column_query)
            print("✅ Колонка is_subscribed добавлена")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("✅ Колонка is_subscribed уже существует")
            else:
                print(f"❌ Ошибка добавления колонки: {e}")
                return False
        
        print("\n🔄 Этап 3: Синхронизация данных...")
        
        if has_subscription_active:
            # Синхронизируем is_subscribed с subscription_active
            sync_query = """
                UPDATE users 
                SET is_subscribed = subscription_active 
                WHERE is_subscribed IS NULL OR is_subscribed != subscription_active
            """
            
            try:
                await adapter.execute(sync_query)
                print("✅ Данные синхронизированы с subscription_active")
            except Exception as e:
                print(f"⚠️ Не удалось синхронизировать данные: {e}")
        else:
            # Устанавливаем значения по умолчанию
            default_query = """
                UPDATE users 
                SET is_subscribed = FALSE 
                WHERE is_subscribed IS NULL
            """
            
            try:
                await adapter.execute(default_query)
                print("✅ Установлены значения по умолчанию")
            except Exception as e:
                print(f"⚠️ Не удалось установить значения по умолчанию: {e}")
        
        print("\n📊 Этап 4: Финальная проверка...")
        
        # Проверяем результат
        check_query = """
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN is_subscribed = TRUE THEN 1 END) as subscribed_users,
                COUNT(CASE WHEN is_subscribed IS NULL THEN 1 END) as null_values
            FROM users
        """
        
        result = await adapter.fetch_one(check_query)
        if result:
            total, subscribed, nulls = result
            print(f"📈 Статистика пользователей:")
            print(f"   - Всего: {total}")
            print(f"   - С подпиской: {subscribed}")
            print(f"   - NULL значений: {nulls}")
        
        print("\n✅ Исправление колонки is_subscribed завершено успешно!")
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
    success = await fix_subscription_column()
    
    if success:
        print("\n🔄 Рекомендуется перезапустить бота для применения изменений")
        return True
    else:
        print("\n❌ Исправление не удалось")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
