#!/usr/bin/env python3
"""
Тестовый скрипт для проверки unified сервиса локально
"""

import asyncio
import logging
import os
import sys
import time
import requests
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)


async def test_database_connection():
    """Тест подключения к базе данных"""
    try:
        logger.info("🔍 Тестирование подключения к БД...")
        from database.production_manager import ProductionDatabaseManager
        
        db_manager = ProductionDatabaseManager()
        await db_manager.adapter.connect()
        
        # Простой запрос
        result = await db_manager.adapter.execute_query("SELECT 1 as test")
        await db_manager.adapter.disconnect()
        
        if result:
            logger.info("✅ База данных доступна")
            return True
        else:
            logger.error("❌ Проблемы с БД")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        return False


def test_environment_variables():
    """Тест переменных окружения"""
    logger.info("🔍 Проверка переменных окружения...")
    
    required_vars = [
        'DATABASE_URL',
        'BOT_TOKEN',
        'API_ID',
        'API_HASH',
        'ADMIN_USER_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Отсутствуют переменные: {', '.join(missing_vars)}")
        return False
    
    logger.info("✅ Все переменные окружения настроены")
    return True


def test_admin_panel_health():
    """Тест health check админ-панели"""
    logger.info("🔍 Тестирование админ-панели...")
    
    max_attempts = 10
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get('http://localhost:8080/api/health', timeout=5)
            if response.status_code == 200:
                logger.info("✅ Админ-панель отвечает")
                return True
        except Exception as e:
            logger.warning(f"⏳ Попытка {attempt}/{max_attempts}: {e}")
            if attempt < max_attempts:
                time.sleep(2)
    
    logger.error("❌ Админ-панель недоступна")
    return False


async def test_bot_health():
    """Тест health check бота"""
    try:
        logger.info("🔍 Тестирование Telegram бота...")
        from bot.health_check import check_bot_health
        
        is_healthy = await check_bot_health()
        if is_healthy:
            logger.info("✅ Telegram бот здоров")
            return True
        else:
            logger.error("❌ Проблемы с Telegram ботом")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки бота: {e}")
        return False


async def run_tests():
    """Запуск всех тестов"""
    logger.info("🚀 Запуск тестов unified сервиса...")
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("Database Connection", test_database_connection),
        ("Bot Health", test_bot_health),
        ("Admin Panel Health", test_admin_panel_health)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Тест: {test_name}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            results[test_name] = result
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"   {status}")
            
        except Exception as e:
            logger.error(f"   💥 ERROR: {e}")
            results[test_name] = False
    
    # Итоговый отчет
    logger.info("\n" + "="*50)
    logger.info("📊 ИТОГОВЫЙ ОТЧЕТ")
    logger.info("="*50)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        logger.info(f"{status} {test_name}")
    
    logger.info(f"\n📈 Результат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        logger.info("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система готова к работе.")
        return True
    else:
        logger.error("⚠️ ЕСТЬ ПРОБЛЕМЫ! Проверьте конфигурацию.")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("🛑 Тестирование прервано")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)
