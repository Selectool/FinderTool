"""
Тестовый скрипт для проверки работы ChannelFinder
"""
import asyncio
import os
from dotenv import load_dotenv
from services.channel_finder import ChannelFinder

load_dotenv()

async def test_channel_finder():
    """Тест поиска похожих каналов"""
    
    # Получаем конфигурацию
    api_id = int(os.getenv("API_ID", "0"))
    api_hash = os.getenv("API_HASH", "")
    
    if not api_id or not api_hash:
        print("❌ API_ID или API_HASH не настроены!")
        print("Получите их на https://my.telegram.org")
        return
    
    # Создаем экземпляр ChannelFinder
    finder = ChannelFinder(api_id, api_hash, "test_session")
    
    # Тестовые каналы
    test_messages = [
        "https://t.me/durov",
        "@telegram",
        "t.me/vc",
        "Найди похожие каналы для https://t.me/habr_com и @tproger"
    ]
    
    print("🔍 Тестирование поиска похожих каналов...\n")
    
    for i, message in enumerate(test_messages, 1):
        print(f"📝 Тест {i}: {message}")
        print("-" * 50)
        
        try:
            # Ищем похожие каналы
            results = await finder.find_similar_channels(message)
            
            # Выводим результаты
            formatted_result = finder.format_results(results)
            print(formatted_result)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        print("\n" + "=" * 60 + "\n")
        
        # Небольшая пауза между запросами
        await asyncio.sleep(2)
    
    # Закрываем клиент
    await finder.close_client()
    print("✅ Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(test_channel_finder())
