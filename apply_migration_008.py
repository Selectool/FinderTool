#!/usr/bin/env python3
"""
Скрипт для применения миграции 008 - исправление схемы БД
"""
import asyncio
import os
import sys
from database.migration_manager import MigrationManager

async def apply_migration():
    """Применить миграцию 008"""
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/telegram_bot')
    manager = MigrationManager(database_url)
    
    print('🚀 Применяем миграцию 008 для исправления схемы БД...')
    try:
        await manager.apply_migration('008')
        print('✅ Миграция 008 успешно применена!')
        return True
    except Exception as e:
        print(f'❌ Ошибка применения миграции: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = asyncio.run(apply_migration())
    sys.exit(0 if success else 1)
