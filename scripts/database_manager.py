#!/usr/bin/env python3
"""
Утилита для управления базой данных в production
"""
import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from database.production_manager import ProductionDatabaseManager
from database.db_adapter import DatabaseAdapter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatabaseManagerCLI:
    """CLI для управления базой данных"""
    
    def __init__(self):
        self.manager = ProductionDatabaseManager()
    
    async def status(self):
        """Показать статус базы данных"""
        logger.info("Проверка статуса базы данных...")
        
        # Информация о базе данных
        info = await self.manager.get_database_info()
        print("\n=== ИНФОРМАЦИЯ О БАЗЕ ДАННЫХ ===")
        print(f"Тип БД: {info.get('database_type', 'unknown')}")
        print(f"URL: {info.get('database_url', 'unknown')}")
        print(f"Статус подключения: {info.get('connection_status', 'unknown')}")
        
        if info.get('error'):
            print(f"Ошибка: {info['error']}")
            return
        
        print(f"\nТаблицы: {len(info.get('tables', []))}")
        for table in info.get('tables', []):
            table_name = table.get('table_name', 'unknown')
            count = info.get(f'{table_name}_count', 'N/A')
            print(f"  - {table_name}: {count} записей")
        
        # Health check
        health = await self.manager.health_check()
        print(f"\n=== ПРОВЕРКА ЗДОРОВЬЯ ===")
        print(f"Статус: {health['status']}")
        if health.get('error'):
            print(f"Ошибка: {health['error']}")
        else:
            for check, result in health.get('checks', {}).items():
                print(f"  - {check}: {result}")
    
    async def migrate(self, force=False):
        """Выполнить миграцию данных"""
        logger.info("Проверка необходимости миграции...")
        
        # Проверяем нужна ли миграция
        migration_needed = await self.manager._check_migration_needed()
        
        if not migration_needed and not force:
            print("Миграция не требуется")
            return
        
        if force:
            print("Принудительная миграция...")
        else:
            print("Требуется миграция данных")
        
        # Подтверждение
        if not force:
            confirm = input("Продолжить миграцию? (y/N): ")
            if confirm.lower() != 'y':
                print("Миграция отменена")
                return
        
        # Выполняем миграцию
        try:
            await self.manager._perform_migration()
            print("Миграция завершена успешно!")
        except Exception as e:
            print(f"Ошибка миграции: {e}")
            logger.error(f"Ошибка миграции: {e}")
    
    async def init(self):
        """Инициализировать базу данных"""
        logger.info("Инициализация базы данных...")
        
        success = await self.manager.initialize_database()
        
        if success:
            print("База данных успешно инициализирована!")
            await self.status()
        else:
            print("Ошибка инициализации базы данных!")
    
    async def backup(self):
        """Создать резервную копию"""
        logger.info("Создание резервной копии...")
        
        try:
            await self.manager._create_backup()
            print("Резервная копия создана успешно!")
        except Exception as e:
            print(f"Ошибка создания резервной копии: {e}")
            logger.error(f"Ошибка создания резервной копии: {e}")
    
    async def cleanup(self, days=30):
        """Очистить старые резервные копии"""
        logger.info(f"Очистка резервных копий старше {days} дней...")
        
        try:
            await self.manager.cleanup_old_backups(days)
            print("Очистка завершена!")
        except Exception as e:
            print(f"Ошибка очистки: {e}")
            logger.error(f"Ошибка очистки: {e}")
    
    async def test_connection(self):
        """Тестировать подключение к базе данных"""
        logger.info("Тестирование подключения...")
        
        try:
            await self.manager._check_connection()
            print("Подключение к базе данных работает!")
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            logger.error(f"Ошибка подключения: {e}")
    
    async def reset_migration_lock(self):
        """Сбросить блокировку миграции"""
        logger.info("Сброс блокировки миграции...")
        
        if os.path.exists(self.manager.migration_lock_file):
            confirm = input("Удалить файл блокировки миграции? (y/N): ")
            if confirm.lower() == 'y':
                os.remove(self.manager.migration_lock_file)
                print("Блокировка миграции сброшена")
            else:
                print("Операция отменена")
        else:
            print("Файл блокировки не найден")


async def main():
    """Главная функция CLI"""
    parser = argparse.ArgumentParser(description='Управление базой данных Telegram Channel Finder Bot')
    parser.add_argument('command', choices=[
        'status', 'migrate', 'init', 'backup', 'cleanup', 
        'test', 'reset-lock'
    ], help='Команда для выполнения')
    parser.add_argument('--force', action='store_true', help='Принудительное выполнение')
    parser.add_argument('--days', type=int, default=30, help='Количество дней для cleanup')
    
    args = parser.parse_args()
    
    cli = DatabaseManagerCLI()
    
    try:
        if args.command == 'status':
            await cli.status()
        elif args.command == 'migrate':
            await cli.migrate(force=args.force)
        elif args.command == 'init':
            await cli.init()
        elif args.command == 'backup':
            await cli.backup()
        elif args.command == 'cleanup':
            await cli.cleanup(args.days)
        elif args.command == 'test':
            await cli.test_connection()
        elif args.command == 'reset-lock':
            await cli.reset_migration_lock()
    
    except KeyboardInterrupt:
        print("\nОперация прервана пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        logger.error(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())
