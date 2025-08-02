#!/usr/bin/env python3
"""
Управление миграциями для Telegram Channel Finder Bot
"""
import asyncio
import sys
import os
from pathlib import Path

# Устанавливаем переменные окружения
os.environ["PYTHONPATH"] = str(Path(__file__).parent)

async def main():
    """Основная функция управления миграциями"""
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1]
    
    # Определяем URL базы данных
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        environment = os.getenv('ENVIRONMENT', 'development')
        if environment == 'production':
            database_url = 'postgresql://findertool_user:Findertool1999!@findertool-hyvrte:5432/findertool_prod'
        else:
            database_url = 'sqlite:///bot.db'
    
    print(f"🔗 Используется БД: {database_url}")
    
    from database.migration_manager import MigrationManager
    manager = MigrationManager(database_url)
    
    if command == "migrate":
        print("🚀 Применение всех миграций...")
        await manager.migrate()
        
    elif command == "status":
        print("📊 Статус миграций...")
        await manager.status()
        
    elif command == "create":
        if len(sys.argv) < 3:
            print("❌ Укажите описание миграции: python manage_migrations.py create 'Описание миграции'")
            return
        
        description = sys.argv[2]
        filename = manager.create_migration(description)
        print(f"✅ Создана миграция: {filename}")
        print(f"📝 Отредактируйте файл: database/migrations/{filename}")
        
    elif command == "rollback":
        if len(sys.argv) < 3:
            print("❌ Укажите версию миграции: python manage_migrations.py rollback 001")
            return
        
        version = sys.argv[2]
        print(f"⏪ Откат миграции {version}...")
        await manager.rollback_migration(version)
        
    elif command == "init":
        print("🔧 Инициализация системы миграций...")
        await manager.init_migrations_table()
        print("✅ Система миграций инициализирована")
        
    elif command == "reset":
        print("⚠️ ВНИМАНИЕ: Это удалит ВСЕ данные!")
        confirm = input("Введите 'YES' для подтверждения: ")
        if confirm == "YES":
            await reset_database(manager)
        else:
            print("❌ Операция отменена")
            
    elif command == "sync":
        print("🔄 Синхронизация с production...")
        await sync_with_production(manager)
        
    else:
        print(f"❌ Неизвестная команда: {command}")
        print_help()

def print_help():
    """Показать справку по командам"""
    print("""
🛠️ Управление миграциями Telegram Channel Finder Bot

Команды:
  migrate              Применить все неприменённые миграции
  status               Показать статус миграций
  create <описание>    Создать новую миграцию
  rollback <версия>    Откатить миграцию
  init                 Инициализировать систему миграций
  reset                Сбросить базу данных (ОПАСНО!)
  sync                 Синхронизировать с production

Примеры:
  python manage_migrations.py migrate
  python manage_migrations.py status
  python manage_migrations.py create "Добавить таблицу платежей"
  python manage_migrations.py rollback 003

Переменные окружения:
  DATABASE_URL         URL базы данных
  ENVIRONMENT          Окружение (development/production)
""")

async def reset_database(manager):
    """Сбросить базу данных"""
    print("🗑️ Сброс базы данных...")
    
    # Получаем все примененные миграции в обратном порядке
    applied_migrations = await manager.get_applied_migrations()
    applied_migrations.reverse()
    
    # Откатываем все миграции
    for version in applied_migrations:
        try:
            print(f"⏪ Откат миграции {version}...")
            await manager.rollback_migration(version)
        except Exception as e:
            print(f"⚠️ Ошибка отката миграции {version}: {e}")
    
    print("✅ База данных сброшена")

async def sync_with_production(manager):
    """Синхронизировать локальную базу с production"""
    print("🔄 Синхронизация с production...")
    
    # Применяем все миграции
    await manager.migrate()
    
    print("✅ Синхронизация завершена")
    print("🎯 Теперь локальная база соответствует production")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Операция прервана пользователем")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
