#!/usr/bin/env python3
"""
Тестирование API статистики рассылок
"""
import asyncio
import aiohttp
import json

async def test_broadcast_stats():
    """Тестировать API статистики рассылки"""
    
    # Тестируем рассылку #2
    broadcast_id = 2
    
    async with aiohttp.ClientSession() as session:
        # Тестируем API статистики
        try:
            async with session.get(f"http://localhost:8001/api/broadcasts/{broadcast_id}/stats") as response:
                print(f"Статус ответа: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print("Статистика рассылки:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                else:
                    text = await response.text()
                    print(f"Ошибка: {text}")
        except Exception as e:
            print(f"Ошибка при запросе статистики: {e}")
        
        # Тестируем веб-страницу
        try:
            async with session.get(f"http://localhost:8001/broadcasts/{broadcast_id}") as response:
                print(f"\nСтатус веб-страницы: {response.status}")
                if response.status != 200:
                    text = await response.text()
                    print(f"Ошибка веб-страницы: {text}")
                else:
                    print("Веб-страница загружается успешно")
        except Exception as e:
            print(f"Ошибка при загрузке веб-страницы: {e}")

if __name__ == "__main__":
    asyncio.run(test_broadcast_stats())
