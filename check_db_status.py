#!/usr/bin/env python3
"""
Проверка состояния базы данных PostgreSQL
"""
import asyncio
import os
import sys

# Устанавливаем переменные окружения
os.environ["ENVIRONMENT"] = "production"
os.environ["PYTHONPATH"] = "/app"

async def check_database():
    """Проверить состояние базы данных"""
    try:
        from database.db_adapter import DatabaseAdapter
        
        database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999!@findertool-hyvrte:5432/findertool_prod')
        print(f"🔗 Подключение к БД: {database_url}")
        
        adapter = DatabaseAdapter(database_url)
        await adapter.connect()
        
        print("✅ Подключение к PostgreSQL успешно")
        
        # Проверяем существующие таблицы
        tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """
        
        tables = await adapter.fetch_all(tables_query)
        print(f"\n📋 Найдено таблиц: {len(tables)}")

        # Обрабатываем результат в зависимости от типа
        table_names = []
        if tables:
            for table in tables:
                if isinstance(table, (list, tuple)):
                    table_names.append(table[0])
                elif isinstance(table, dict):
                    table_names.append(table['table_name'])
                else:
                    table_names.append(str(table))

        print(f"🔍 Обработано таблиц: {len(table_names)}")
        
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
                count_query = f"SELECT COUNT(*) FROM {table}"
                result = await adapter.fetch_one(count_query)
                count = result[0] if result else 0
                print(f"✅ {table}: {count} записей")
            else:
                print(f"❌ {table}: НЕ НАЙДЕНА")
        
        print(f"\n📋 Все таблицы в БД:")
        for table in table_names:
            print(f"   • {table}")
        
        # Специальная проверка admin_users
        if 'admin_users' in table_names:
            print(f"\n👤 Проверка таблицы admin_users:")
            
            # Структура таблицы
            columns_query = """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'admin_users' 
                ORDER BY ordinal_position;
            """
            columns = await adapter.fetch_all(columns_query)

            print("📋 Структура таблицы admin_users:")
            for col in columns:
                if isinstance(col, (list, tuple)):
                    print(f"   • {col[0]} ({col[1]}) - nullable: {col[2]}")
                elif isinstance(col, dict):
                    print(f"   • {col['column_name']} ({col['data_type']}) - nullable: {col['is_nullable']}")
                else:
                    print(f"   • {col}")
            
            # Проверяем пользователей
            users_query = "SELECT username, role, is_active, created_at FROM admin_users"
            users = await adapter.fetch_all(users_query)

            print(f"\n👥 Пользователи в admin_users ({len(users)}):")
            for user in users:
                if isinstance(user, (list, tuple)):
                    print(f"   • {user[0]} ({user[1]}) - активен: {user[2]} - создан: {user[3]}")
                elif isinstance(user, dict):
                    print(f"   • {user['username']} ({user['role']}) - активен: {user['is_active']} - создан: {user['created_at']}")
                else:
                    print(f"   • {user}")
        
        await adapter.disconnect()
        print("\n✅ Проверка завершена")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка проверки БД: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔍 Проверка состояния базы данных PostgreSQL...")
    success = asyncio.run(check_database())
    
    if success:
        print("\n🎯 Рекомендации:")
        print("1. Если таблица admin_users отсутствует - запустите: python fix_admin_table.py")
        print("2. Если таблица есть, но пуста - запустите: python fix_admin_table.py")
        print("3. Если все в порядке - запустите обычный перезапуск")
    else:
        print("\n❌ Проблемы с подключением к БД")
    
    sys.exit(0 if success else 1)
