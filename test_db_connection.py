#!/usr/bin/env python3
"""
Тест подключения к PostgreSQL
"""
import asyncio
import asyncpg
import os

async def test_connection():
    """Тестировать подключение к БД"""
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/telegram_bot')
    
    print(f'🔗 Тестируем подключение к: {database_url}')
    
    try:
        # Пробуем подключиться
        conn = await asyncpg.connect(database_url)
        print('✅ Подключение успешно!')
        
        # Проверяем версию PostgreSQL
        version = await conn.fetchval('SELECT version()')
        print(f'📊 Версия PostgreSQL: {version}')
        
        # Проверяем существующие таблицы
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        print(f'📋 Найдено таблиц: {len(tables)}')
        for table in tables:
            print(f'  - {table["table_name"]}')
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f'❌ Ошибка подключения: {e}')
        return False

if __name__ == '__main__':
    success = asyncio.run(test_connection())
    exit(0 if success else 1)
