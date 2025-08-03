#!/usr/bin/env python3
"""
Тест исправлений для подсчета пользователей
"""
import asyncio
import os
from database.universal_database import UniversalDatabase

async def test_database_fixes():
    """Тестирование исправлений базы данных"""
    try:
        print("🔧 Тестирование исправлений базы данных...")
        
        # Создаем экземпляр UniversalDatabase
        db = UniversalDatabase()
        print(f"✅ UniversalDatabase создан с URL: {db.database_url[:50]}...")
        
        # Подключаемся к базе
        await db.adapter.connect()
        print("✅ Подключение к базе данных установлено")
        
        # Тестируем прямой запрос
        print("\n📊 Тестирование прямого запроса...")
        result = await db.adapter.fetch_one('SELECT COUNT(*) FROM users')
        print(f"Результат запроса: {result}")
        print(f"Тип результата: {type(result)}")
        
        if result:
            if hasattr(result, 'keys'):
                print(f"Ключи: {list(result.keys())}")
            if hasattr(result, 'values'):
                print(f"Значения: {list(result.values())}")
        
        # Тестируем _extract_count
        print("\n🔍 Тестирование _extract_count...")
        count = db._extract_count(result)
        print(f"Извлеченное количество: {count}")
        
        # Тестируем get_stats
        print("\n📈 Тестирование get_stats...")
        stats = await db.get_stats()
        print(f"Статистика: {stats}")
        
        # Тестируем get_users_count
        print("\n👥 Тестирование get_users_count...")
        users_count = await db.get_users_count()
        print(f"Количество пользователей: {users_count}")
        
        # Тестируем get_subscribers_count
        print("\n💎 Тестирование get_subscribers_count...")
        subs_count = await db.get_subscribers_count()
        print(f"Количество подписчиков: {subs_count}")
        
        # Тестируем get_users_paginated
        print("\n📄 Тестирование get_users_paginated...")
        users_data = await db.get_users_paginated(page=1, per_page=10)
        print(f"Пагинированные пользователи: всего {users_data['total']}, на странице {len(users_data['users'])}")
        
        await db.adapter.disconnect()
        print("\n✅ Все тесты завершены успешно!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_database_fixes())
    if success:
        print("\n🎉 Исправления работают корректно!")
    else:
        print("\n💥 Требуются дополнительные исправления!")
