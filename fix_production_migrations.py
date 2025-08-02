#!/usr/bin/env python3
"""
Production-ready скрипт для исправления проблем с миграциями
Решает конфликт между AdminMigrations и MigrationManager
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from database.unified_migration_manager import UnifiedMigrationManager, fix_migration_conflicts

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция исправления миграций"""
    
    print("🚀 Production Migration Fix Tool")
    print("=" * 50)
    
    # Получаем URL базы данных
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        database_url = 'postgresql://findertool_user:Findertool1999@localhost:5432/findertool_prod'
        print(f"⚠️ DATABASE_URL не установлен, используем: {database_url}")
    else:
        print(f"🔗 Используется БД: {database_url}")
    
    try:
        print("\n📊 Этап 1: Диагностика проблемы...")
        
        # Создаем менеджер миграций
        manager = UnifiedMigrationManager(database_url)
        
        print("🔍 Проверяем структуру таблицы schema_migrations...")
        
        # Проверяем текущее состояние
        from database.db_adapter import DatabaseAdapter
        adapter = DatabaseAdapter(database_url)
        await adapter.connect()
        
        try:
            # Проверяем существование таблицы
            if manager.db_type == 'postgresql':
                check_query = """
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'schema_migrations'
                    ORDER BY ordinal_position
                """
            else:
                check_query = "PRAGMA table_info(schema_migrations)"
            
            columns = await adapter.fetch_all(check_query)
            
            if columns:
                print("📋 Текущие колонки в schema_migrations:")
                for col in columns:
                    if manager.db_type == 'postgresql':
                        print(f"   - {col[0]} ({col[1]})")
                    else:
                        print(f"   - {col[1]} ({col[2]})")
                
                # Проверяем наличие migration_name
                column_names = [col[0] if manager.db_type == 'postgresql' else col[1] for col in columns]
                if 'migration_name' not in column_names:
                    print("❌ Проблема: отсутствует колонка migration_name")
                else:
                    print("✅ Колонка migration_name присутствует")
            else:
                print("❌ Таблица schema_migrations не существует")
        
        finally:
            await adapter.disconnect()
        
        print("\n🔧 Этап 2: Исправление структуры таблицы...")
        
        # Исправляем таблицу миграций
        success = await manager.fix_schema_migrations_table()
        
        if success:
            print("✅ Структура таблицы schema_migrations исправлена")
        else:
            print("❌ Не удалось исправить структуру таблицы")
            return False
        
        print("\n🔄 Этап 3: Запуск админ миграций...")
        
        # Запускаем админ миграции с исправленной системой
        admin_success = await manager.run_admin_migrations_fix()
        
        if admin_success:
            print("✅ Админ миграции выполнены успешно")
        else:
            print("⚠️ Проблемы с админ миграциями, но основная структура исправлена")
        
        print("\n📊 Этап 4: Финальная проверка...")
        
        # Финальная проверка
        adapter = DatabaseAdapter(database_url)
        await adapter.connect()
        
        try:
            # Проверяем количество записей в миграциях
            count_query = "SELECT COUNT(*) FROM schema_migrations"
            result = await adapter.fetch_one(count_query)
            migration_count = result[0] if result else 0
            
            print(f"📈 Записей в schema_migrations: {migration_count}")
            
            # Проверяем последние миграции
            if migration_count > 0:
                recent_query = """
                    SELECT migration_name, applied_at 
                    FROM schema_migrations 
                    ORDER BY applied_at DESC 
                    LIMIT 5
                """
                recent = await adapter.fetch_all(recent_query)
                
                print("📋 Последние миграции:")
                for migration in recent:
                    print(f"   - {migration[0]} ({migration[1]})")
        
        finally:
            await adapter.disconnect()
        
        print("\n✅ Исправление миграций завершено успешно!")
        print("🔄 Теперь можно перезапустить бота")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def quick_fix():
    """Быстрое исправление без детальной диагностики"""
    print("⚡ Быстрое исправление миграций...")
    
    database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999@localhost:5432/findertool_prod')
    
    try:
        success = await fix_migration_conflicts(database_url)
        
        if success:
            print("✅ Быстрое исправление выполнено успешно")
            return True
        else:
            print("❌ Быстрое исправление не удалось")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка быстрого исправления: {e}")
        return False


def print_help():
    """Выводит справку по использованию"""
    print("""
🛠️ Production Migration Fix Tool

Использование:
    python fix_production_migrations.py [команда]

Команды:
    fix     - Полное исправление с диагностикой (по умолчанию)
    quick   - Быстрое исправление без диагностики
    help    - Показать эту справку

Переменные окружения:
    DATABASE_URL - URL базы данных (обязательно для production)

Примеры:
    python fix_production_migrations.py
    python fix_production_migrations.py fix
    python fix_production_migrations.py quick
    
    # С указанием БД
    DATABASE_URL="postgresql://user:pass@host:5432/db" python fix_production_migrations.py
""")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "fix"
    
    if command == "help":
        print_help()
    elif command == "quick":
        success = asyncio.run(quick_fix())
        sys.exit(0 if success else 1)
    elif command == "fix":
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    else:
        print(f"❌ Неизвестная команда: {command}")
        print_help()
        sys.exit(1)
