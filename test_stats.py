#!/usr/bin/env python3
"""
Тест статистики пользователей
"""
import asyncio
import os
from database.universal_database import UniversalDatabase

async def test_stats():
    try:
        print("Тестирование статистики...")
        db = UniversalDatabase()
        
        # Тест get_stats
        print("Получение статистики...")
        stats = await db.get_stats()
        print(f"Stats: {stats}")
        
        # Прямой запрос к базе
        print("Прямой запрос к базе...")
        await db.adapter.connect()
        
        # Проверяем количество пользователей
        result = await db.adapter.fetch_one('SELECT COUNT(*) FROM users')
        print(f"Direct users count: {result}")
        
        # Проверяем структуру результата
        print(f"Result type: {type(result)}")
        if result:
            print(f"Result keys: {result.keys() if hasattr(result, 'keys') else 'No keys'}")
            print(f"Result values: {list(result.values()) if hasattr(result, 'values') else 'No values'}")
        
        # Проверяем метод _extract_count
        count = db._extract_count(result)
        print(f"Extracted count: {count}")
        
        await db.adapter.disconnect()
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_stats())
