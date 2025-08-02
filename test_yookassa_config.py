#!/usr/bin/env python3
"""
Тестирование конфигурации ЮKassa
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def test_yookassa_config():
    """Тестирование конфигурации ЮKassa"""
    print("=== ТЕСТИРОВАНИЕ КОНФИГУРАЦИИ ЮKASSA ===")
    
    # Получаем переменные
    mode = os.getenv("YOOKASSA_MODE", "TEST")
    test_token = os.getenv("YOOKASSA_TEST_TOKEN", "")
    live_token = os.getenv("YOOKASSA_LIVE_TOKEN", "")
    
    print(f"Режим: {mode}")
    print(f"Тестовый токен: {test_token}")
    print(f"Продакшн токен: {live_token}")
    print()
    
    # Определяем активный токен
    active_token = test_token if mode == "TEST" else live_token
    print(f"Активный токен: {active_token}")
    
    # Проверяем формат токена
    if mode == "LIVE":
        if ":LIVE:" in active_token:
            print("✅ LIVE токен имеет правильный формат")
        else:
            print("❌ LIVE токен должен содержать ':LIVE:'")
    else:
        if ":TEST:" in active_token:
            print("✅ TEST токен имеет правильный формат")
        else:
            print("❌ TEST токен должен содержать ':TEST:'")
    
    # Проверяем структуру токена
    parts = active_token.split(":")
    if len(parts) >= 3:
        shop_id = parts[0]
        token_type = parts[1]
        secret = parts[2]
        
        print(f"Shop ID: {shop_id}")
        print(f"Тип токена: {token_type}")
        print(f"Секретный ключ: {secret[:10]}...{secret[-10:] if len(secret) > 20 else secret}")
    else:
        print("❌ Неправильная структура токена")
    
    print()
    
    # Тестируем импорт config
    try:
        from config import YOOKASSA_PROVIDER_TOKEN, YOOKASSA_MODE
        print(f"Конфигурация загружена:")
        print(f"  Режим из config.py: {YOOKASSA_MODE}")
        print(f"  Токен из config.py: {YOOKASSA_PROVIDER_TOKEN}")
        
        # Проверяем режим
        is_live = ":LIVE:" in YOOKASSA_PROVIDER_TOKEN
        print(f"  Определенный режим: {'LIVE' if is_live else 'TEST'}")
        
        if YOOKASSA_MODE == "LIVE" and is_live:
            print("✅ Конфигурация корректна для LIVE режима")
        elif YOOKASSA_MODE == "TEST" and not is_live:
            print("✅ Конфигурация корректна для TEST режима")
        else:
            print("❌ Несоответствие между YOOKASSA_MODE и токеном")
            
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")

if __name__ == "__main__":
    test_yookassa_config()
