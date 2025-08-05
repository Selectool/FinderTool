#!/usr/bin/env python3
"""
Скрипт для исправления проблем с базой данных
"""
import asyncio
import asyncpg
import os

async def fix_database():
    """Исправить проблемы с базой данных"""
    
    # Сначала подключаемся к базе postgres по умолчанию
    default_url = 'postgresql://postgres:postgres@localhost:5432/postgres'
    target_db = 'telegram_bot'
    
    print(f'🔗 Подключаемся к PostgreSQL...')
    
    try:
        # Подключаемся к базе postgres
        conn = await asyncpg.connect(default_url)
        print('✅ Подключение к PostgreSQL успешно!')
        
        # Проверяем существование базы telegram_bot
        db_exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM pg_database WHERE datname = $1
            )
        """, target_db)
        
        if not db_exists:
            print(f'📝 Создаем базу данных {target_db}...')
            await conn.execute(f'CREATE DATABASE {target_db}')
            print(f'✅ База данных {target_db} создана!')
        else:
            print(f'ℹ️ База данных {target_db} уже существует')
        
        await conn.close()
        
        # Теперь подключаемся к целевой базе
        target_url = f'postgresql://postgres:postgres@localhost:5432/{target_db}'
        conn = await asyncpg.connect(target_url)
        print(f'✅ Подключение к {target_db} успешно!')
        
        # Проверяем таблицы
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        print(f'📋 Найдено таблиц: {len(tables)}')
        for table in tables:
            print(f'  - {table["table_name"]}')
        
        # Проверяем проблемные столбцы
        print('\n🔍 Проверяем структуру таблиц...')
        
        # Проверяем users
        if any(t['table_name'] == 'users' for t in tables):
            user_columns = await conn.fetch("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            print(f'👤 Столбцы таблицы users ({len(user_columns)}):')
            for col in user_columns:
                print(f'  - {col["column_name"]} ({col["data_type"]})')
        
        # Проверяем payments
        if any(t['table_name'] == 'payments' for t in tables):
            payment_columns = await conn.fetch("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'payments' AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            print(f'💳 Столбцы таблицы payments ({len(payment_columns)}):')
            for col in payment_columns:
                print(f'  - {col["column_name"]} ({col["data_type"]})')
        
        await conn.close()
        print('\n✅ Диагностика завершена!')
        return True
        
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = asyncio.run(fix_database())
    exit(0 if success else 1)
