#!/usr/bin/env python3
"""
Комплексное исправление всех проблем production-сервера
- Исправление миграций
- Добавление колонки is_subscribed
- Проверка целостности базы данных
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_migration_fix():
    """Запускает исправление миграций"""
    print("🔧 Исправление системы миграций...")
    
    try:
        from database.unified_migration_manager import fix_migration_conflicts
        database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999@localhost:5432/findertool_prod')
        
        success = await fix_migration_conflicts(database_url)
        
        if success:
            print("✅ Система миграций исправлена")
            return True
        else:
            print("❌ Не удалось исправить систему миграций")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка исправления миграций: {e}")
        return False


async def run_subscription_fix():
    """Запускает исправление колонки is_subscribed"""
    print("🔧 Исправление колонки is_subscribed...")
    
    try:
        from database.db_adapter import DatabaseAdapter
        
        database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999@localhost:5432/findertool_prod')
        db_type = 'postgresql' if database_url.startswith('postgresql') else 'sqlite'
        
        adapter = DatabaseAdapter(database_url)
        await adapter.connect()
        
        try:
            # Проверяем наличие колонки
            if db_type == 'postgresql':
                check_query = """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'is_subscribed'
                """
            else:
                check_query = "PRAGMA table_info(users)"
            
            result = await adapter.fetch_all(check_query)
            
            if db_type == 'postgresql':
                has_column = len(result) > 0
            else:
                has_column = any(col[1] == 'is_subscribed' for col in result)
            
            if not has_column:
                # Добавляем колонку
                if db_type == 'postgresql':
                    add_query = "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_subscribed BOOLEAN DEFAULT FALSE"
                else:
                    add_query = "ALTER TABLE users ADD COLUMN is_subscribed BOOLEAN DEFAULT FALSE"
                
                await adapter.execute(add_query)
                print("✅ Колонка is_subscribed добавлена")
            else:
                print("✅ Колонка is_subscribed уже существует")
            
            # Синхронизируем данные
            sync_query = """
                UPDATE users 
                SET is_subscribed = COALESCE(subscription_active, FALSE) 
                WHERE is_subscribed IS NULL OR is_subscribed != COALESCE(subscription_active, FALSE)
            """
            
            await adapter.execute(sync_query)
            print("✅ Данные синхронизированы")
            
            return True
            
        finally:
            await adapter.disconnect()
            
    except Exception as e:
        print(f"❌ Ошибка исправления колонки: {e}")
        return False


async def check_database_health():
    """Проверяет здоровье базы данных"""
    print("🏥 Проверка здоровья базы данных...")
    
    try:
        from database.db_adapter import DatabaseAdapter
        
        database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999@localhost:5432/findertool_prod')
        adapter = DatabaseAdapter(database_url)
        await adapter.connect()
        
        try:
            # Проверяем основные таблицы
            essential_tables = ['users', 'requests', 'payments', 'schema_migrations']
            
            for table in essential_tables:
                try:
                    count_query = f"SELECT COUNT(*) FROM {table}"
                    result = await adapter.fetch_one(count_query)
                    count = result[0] if result else 0
                    print(f"   ✅ {table}: {count} записей")
                except Exception as e:
                    print(f"   ❌ {table}: ошибка - {e}")
            
            # Проверяем индексы
            print("🔍 Проверка индексов...")
            
            if adapter.db_type == 'postgresql':
                indexes_query = """
                    SELECT schemaname, tablename, indexname 
                    FROM pg_indexes 
                    WHERE schemaname = 'public'
                    ORDER BY tablename, indexname
                """
                indexes = await adapter.fetch_all(indexes_query)
                print(f"   📊 Найдено индексов: {len(indexes)}")
            
            print("✅ Проверка здоровья завершена")
            return True
            
        finally:
            await adapter.disconnect()
            
    except Exception as e:
        print(f"❌ Ошибка проверки здоровья: {e}")
        return False


async def optimize_database():
    """Оптимизирует базу данных"""
    print("⚡ Оптимизация базы данных...")
    
    try:
        from database.db_adapter import DatabaseAdapter
        
        database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999@localhost:5432/findertool_prod')
        adapter = DatabaseAdapter(database_url)
        await adapter.connect()
        
        try:
            if adapter.db_type == 'postgresql':
                # PostgreSQL оптимизации
                optimizations = [
                    "ANALYZE;",  # Обновляем статистику
                    "VACUUM;",   # Очищаем мертвые строки
                ]
                
                for opt_query in optimizations:
                    try:
                        await adapter.execute(opt_query)
                        print(f"   ✅ Выполнено: {opt_query}")
                    except Exception as e:
                        print(f"   ⚠️ Не удалось выполнить {opt_query}: {e}")
            
            print("✅ Оптимизация завершена")
            return True
            
        finally:
            await adapter.disconnect()
            
    except Exception as e:
        print(f"❌ Ошибка оптимизации: {e}")
        return False


async def main():
    """Основная функция комплексного исправления"""
    
    print("🚀 Production Fix Tool - Комплексное исправление")
    print("=" * 60)
    
    # Проверяем переменные окружения
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        database_url = 'postgresql://findertool_user:Findertool1999@localhost:5432/findertool_prod'
        print(f"⚠️ DATABASE_URL не установлен, используем: {database_url}")
    else:
        print(f"🔗 Используется БД: {database_url}")
    
    success_count = 0
    total_steps = 4
    
    # Этап 1: Исправление миграций
    print(f"\n📋 Этап 1/{total_steps}: Исправление системы миграций")
    if await run_migration_fix():
        success_count += 1
    
    # Этап 2: Исправление колонки подписки
    print(f"\n📋 Этап 2/{total_steps}: Исправление колонки is_subscribed")
    if await run_subscription_fix():
        success_count += 1
    
    # Этап 3: Проверка здоровья
    print(f"\n📋 Этап 3/{total_steps}: Проверка здоровья базы данных")
    if await check_database_health():
        success_count += 1
    
    # Этап 4: Оптимизация
    print(f"\n📋 Этап 4/{total_steps}: Оптимизация базы данных")
    if await optimize_database():
        success_count += 1
    
    # Итоги
    print(f"\n📊 Результаты исправления:")
    print(f"   ✅ Успешно: {success_count}/{total_steps}")
    print(f"   ❌ Ошибок: {total_steps - success_count}/{total_steps}")
    
    if success_count == total_steps:
        print("\n🎉 Все исправления выполнены успешно!")
        print("🔄 Теперь можно перезапустить бота:")
        print("   python main.py")
        return True
    elif success_count >= 2:
        print("\n⚠️ Основные исправления выполнены, бот должен работать")
        print("🔄 Рекомендуется перезапустить бота:")
        print("   python main.py")
        return True
    else:
        print("\n❌ Критические ошибки, требуется ручное вмешательство")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
