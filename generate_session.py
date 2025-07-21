"""
Утилита для генерации строковой сессии Telethon для production
Запускается ОДИН РАЗ локально для получения строки сессии
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv
import os

load_dotenv()

async def generate_string_session():
    """Генерация строковой сессии"""
    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")
    
    print("🔐 Генерация строковой сессии для production...")
    print("⚠️  ВНИМАНИЕ: Эта утилита запускается ТОЛЬКО ОДИН РАЗ локально!")
    print("📱 Вам потребуется ввести номер телефона и код подтверждения\n")
    
    # Создаем клиент с пустой строковой сессией
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        print("✅ Успешная аутентификация!")
        
        # Получаем строку сессии
        session_string = client.session.save()
        
        print("\n" + "="*60)
        print("🎯 СТРОКА СЕССИИ ДЛЯ PRODUCTION:")
        print("="*60)
        print(session_string)
        print("="*60)
        
        print("\n📋 Инструкции:")
        print("1. Скопируйте строку выше")
        print("2. Добавьте в .env файл:")
        print(f"   SESSION_STRING={session_string}")
        print("3. Обновите код для использования строковой сессии")
        print("4. ⚠️  НИКОГДА НЕ ПУБЛИКУЙТЕ ЭТУ СТРОКУ!")
        
        return session_string

if __name__ == "__main__":
    asyncio.run(generate_string_session())
