#!/usr/bin/env python3
"""
Простая проверка состояния базы данных PostgreSQL
"""
import asyncio
import os
import sys

# Устанавливаем переменные окружения
os.environ["ENVIRONMENT"] = "production"
os.environ["PYTHONPATH"] = "/app"

async def simple_check():
    """Простая проверка базы данных"""
    try:
        import asyncpg
        
        database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999!@findertool-hyvrte:5432/findertool_prod')
        print(f"🔗 Подключение к БД...")
        
        # Парсим URL
        import urllib.parse
        parsed = urllib.parse.urlparse(database_url)
        
        conn = await asyncpg.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:]  # убираем первый слеш
        )
        
        print("✅ Подключение к PostgreSQL успешно")
        
        # Проверяем таблицы
        tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """
        
        tables = await conn.fetch(tables_query)
        print(f"\n📋 Найдено таблиц: {len(tables)}")
        
        table_names = [row['table_name'] for row in tables]
        
        # Критически важные таблицы
        critical_tables = [
            'users',
            'broadcast_messages', 
            'admin_users',
            'roles',
            'message_templates'
        ]
        
        print("\n🔍 Проверка критически важных таблиц:")
        for table in critical_tables:
            if table in table_names:
                # Проверяем количество записей
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                print(f"✅ {table}: {count} записей")
            else:
                print(f"❌ {table}: НЕ НАЙДЕНА")
        
        print(f"\n📋 Все таблицы в БД:")
        for table in table_names:
            print(f"   • {table}")
        
        # Специальная проверка admin_users
        if 'admin_users' in table_names:
            print(f"\n👤 Проверка таблицы admin_users:")
            
            # Проверяем пользователей
            users = await conn.fetch("SELECT username, role, is_active, created_at FROM admin_users")
            
            print(f"\n👥 Пользователи в admin_users ({len(users)}):")
            for user in users:
                print(f"   • {user['username']} ({user['role']}) - активен: {user['is_active']} - создан: {user['created_at']}")
        
        await conn.close()
        print("\n✅ Проверка завершена")
        
        # Выводим рекомендации
        if 'admin_users' not in table_names:
            print("\n🎯 ПРОБЛЕМА: Таблица admin_users отсутствует!")
            print("🔧 РЕШЕНИЕ: Запустите python fix_admin_table.py")
            return False
        elif 'admin_users' in table_names:
            users_count = await conn.fetchval("SELECT COUNT(*) FROM admin_users") if 'admin_users' in table_names else 0
            if users_count == 0:
                print("\n🎯 ПРОБЛЕМА: Таблица admin_users пуста!")
                print("🔧 РЕШЕНИЕ: Запустите python fix_admin_table.py")
                return False
            else:
                print("\n✅ Таблица admin_users в порядке!")
                print("🚀 МОЖНО ЗАПУСКАТЬ: python fix_admin_table.py (для перезапуска)")
                return True
        
        return True
        
    except ImportError:
        print("❌ Модуль asyncpg не найден, пробуем через db_adapter...")
        return await fallback_check()
    except Exception as e:
        print(f"❌ Ошибка проверки БД: {e}")
        import traceback
        traceback.print_exc()
        return False

async def fallback_check():
    """Резервная проверка через db_adapter"""
    try:
        from database.db_adapter import DatabaseAdapter
        
        database_url = os.getenv('DATABASE_URL')
        adapter = DatabaseAdapter(database_url)
        await adapter.connect()
        
        print("✅ Подключение через db_adapter успешно")
        
        # Простая проверка admin_users
        try:
            result = await adapter.execute("SELECT COUNT(*) FROM admin_users")
            print("✅ Таблица admin_users существует")
            
            users = await adapter.fetch_all("SELECT username, role FROM admin_users LIMIT 5")
            print(f"👥 Найдено пользователей: {len(users)}")
            
            await adapter.disconnect()
            return True
            
        except Exception as e:
            if "does not exist" in str(e):
                print("❌ Таблица admin_users НЕ СУЩЕСТВУЕТ")
                print("🔧 РЕШЕНИЕ: Запустите python fix_admin_table.py")
            else:
                print(f"❌ Ошибка проверки admin_users: {e}")
            
            await adapter.disconnect()
            return False
            
    except Exception as e:
        print(f"❌ Ошибка fallback проверки: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Простая проверка состояния базы данных PostgreSQL...")
    success = asyncio.run(simple_check())
    
    if success:
        print("\n🎉 База данных в порядке!")
    else:
        print("\n❌ Обнаружены проблемы с базой данных")
    
    sys.exit(0 if success else 1)
