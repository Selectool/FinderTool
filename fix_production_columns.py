#!/usr/bin/env python3
"""
Скрипт для исправления колонок в production базе данных
Исправляет проблемы с is_subscribed и другими отсутствующими колонками
"""

import asyncio
import os
import sys
import logging
from typing import List, Dict, Any

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_adapter import DatabaseAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_and_fix_columns():
    """Проверить и исправить отсутствующие колонки"""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL не найден в переменных окружения")
        return False
    
    print(f"🔗 Подключение к базе данных...")
    print(f"📊 URL: {database_url.split('@')[0]}@***")
    
    db_type = 'postgresql' if database_url.startswith('postgresql') else 'sqlite'
    print(f"🗄️ Тип БД: {db_type}")
    
    try:
        adapter = DatabaseAdapter(database_url)
        await adapter.connect()
        
        print("\n📊 Этап 1: Проверка структуры таблицы users...")
        
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
                # col может быть dict или tuple, проверяем
                if isinstance(col, dict):
                    column_name = col['column_name']
                    data_type = col['data_type']
                    is_nullable = col['is_nullable']
                else:
                    column_name = col[0]
                    data_type = col[1]
                    is_nullable = col[2]

                column_names.append(column_name)
                print(f"   - {column_name} ({data_type}) {'NULL' if is_nullable == 'YES' else 'NOT NULL'}")
            else:
                column_names.append(col[1])
                print(f"   - {col[1]} ({col[2]}) {'NULL' if col[3] == 0 else 'NOT NULL'}")
        
        # Проверяем наличие нужных колонок
        required_columns = {
            'is_subscribed': 'BOOLEAN DEFAULT FALSE',
            'unlimited_access': 'BOOLEAN DEFAULT FALSE',
            'notes': 'TEXT',
            'blocked': 'BOOLEAN DEFAULT FALSE',
            'bot_blocked': 'BOOLEAN DEFAULT FALSE',
            'blocked_at': 'TIMESTAMP',
            'blocked_by': 'INTEGER',
            'referrer_id': 'INTEGER',
            'registration_source': 'TEXT DEFAULT \'bot\'' if db_type == 'sqlite' else 'VARCHAR(100) DEFAULT \'bot\''
        }
        
        print(f"\n🔍 Анализ обязательных колонок:")
        missing_columns = []
        for col_name, col_def in required_columns.items():
            if col_name in column_names:
                print(f"   - {col_name}: ✅ есть")
            else:
                print(f"   - {col_name}: ❌ нет")
                missing_columns.append((col_name, col_def))
        
        if not missing_columns:
            print("✅ Все обязательные колонки присутствуют")
        else:
            print(f"\n🔧 Этап 2: Добавление недостающих колонок ({len(missing_columns)})...")
            
            for col_name, col_def in missing_columns:
                try:
                    if db_type == 'postgresql':
                        add_query = f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
                    else:
                        add_query = f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"
                    
                    await adapter.execute(add_query)
                    print(f"✅ Добавлена колонка: {col_name}")
                    
                except Exception as e:
                    if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                        print(f"✅ Колонка {col_name} уже существует")
                    else:
                        print(f"❌ Ошибка добавления колонки {col_name}: {e}")
        
        # Проверяем синхронизацию данных
        print(f"\n🔄 Этап 3: Синхронизация данных...")
        
        # Проверяем наличие subscription_active
        has_subscription_active = 'subscription_active' in column_names
        has_is_subscribed = 'is_subscribed' in column_names
        
        if has_subscription_active and has_is_subscribed:
            print("🔄 Синхронизируем is_subscribed с subscription_active...")
            
            if db_type == 'postgresql':
                sync_query = """
                    UPDATE users 
                    SET is_subscribed = COALESCE(subscription_active, FALSE)
                    WHERE is_subscribed IS NULL OR is_subscribed != COALESCE(subscription_active, FALSE)
                """
            else:
                sync_query = """
                    UPDATE users 
                    SET is_subscribed = COALESCE(subscription_active, 0)
                    WHERE is_subscribed IS NULL OR is_subscribed != COALESCE(subscription_active, 0)
                """
            
            try:
                result = await adapter.execute(sync_query)
                print("✅ Данные синхронизированы с subscription_active")
            except Exception as e:
                print(f"⚠️ Не удалось синхронизировать данные: {e}")
        
        elif has_is_subscribed:
            print("🔧 Устанавливаем значения по умолчанию для is_subscribed...")
            
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
        
        print(f"\n📊 Этап 4: Финальная проверка...")
        
        # Проверяем результат
        try:
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
        except Exception as e:
            print(f"⚠️ Не удалось получить статистику: {e}")
        
        print("\n✅ Исправление колонок завершено успешно!")
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
    """Главная функция"""
    print("🔧 ИСПРАВЛЕНИЕ PRODUCTION БАЗЫ ДАННЫХ")
    print("=" * 50)
    
    success = await check_and_fix_columns()
    
    if success:
        print("\n🎉 Все исправления применены успешно!")
        print("🔄 Теперь можно перезапустить бот и админ-панель")
    else:
        print("\n❌ Исправления не удалось применить")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
