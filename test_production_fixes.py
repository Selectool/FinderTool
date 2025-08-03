#!/usr/bin/env python3
"""
Тестирование исправлений для production окружения
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from database.production_manager import ProductionDatabaseManager
from services.payment_cleanup import PaymentCleanupService
from database.universal_database import UniversalDatabase

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_production_database_manager():
    """Тест ProductionDatabaseManager"""
    logger.info("🔧 Тестирование ProductionDatabaseManager...")
    
    try:
        db_manager = ProductionDatabaseManager()
        
        # Тест get_stats
        logger.info("Тестирование get_stats...")
        stats = await db_manager.get_stats()
        logger.info(f"✅ get_stats: {stats}")
        
        # Тест get_detailed_stats
        logger.info("Тестирование get_detailed_stats...")
        detailed_stats = await db_manager.get_detailed_stats()
        logger.info(f"✅ get_detailed_stats: {detailed_stats}")
        
        # Тест get_users_paginated
        logger.info("Тестирование get_users_paginated...")
        users = await db_manager.get_users_paginated(page=1, per_page=10)
        logger.info(f"✅ get_users_paginated: найдено {users['total']} пользователей")
        
        # Тест get_broadcasts_paginated
        logger.info("Тестирование get_broadcasts_paginated...")
        broadcasts = await db_manager.get_broadcasts_paginated(page=1, per_page=10)
        logger.info(f"✅ get_broadcasts_paginated: найдено {broadcasts['total']} рассылок")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в ProductionDatabaseManager: {e}")
        import traceback
        logger.error(f"Полная ошибка: {traceback.format_exc()}")
        return False

async def test_payment_cleanup_service():
    """Тест PaymentCleanupService"""
    logger.info("🧹 Тестирование PaymentCleanupService...")
    
    try:
        # Создаем экземпляр UniversalDatabase для совместимости
        db = UniversalDatabase()
        cleanup_service = PaymentCleanupService(db)
        
        # Тест get_cleanup_statistics
        logger.info("Тестирование get_cleanup_statistics...")
        stats = await cleanup_service.get_cleanup_statistics()
        logger.info(f"✅ get_cleanup_statistics: {stats}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в PaymentCleanupService: {e}")
        import traceback
        logger.error(f"Полная ошибка: {traceback.format_exc()}")
        return False

async def main():
    """Основная функция тестирования"""
    logger.info("=" * 60)
    logger.info("🚀 ТЕСТИРОВАНИЕ PRODUCTION ИСПРАВЛЕНИЙ")
    logger.info("=" * 60)
    
    success_count = 0
    total_tests = 2
    
    # Тест ProductionDatabaseManager
    if await test_production_database_manager():
        success_count += 1
    
    # Тест PaymentCleanupService
    if await test_payment_cleanup_service():
        success_count += 1
    
    logger.info("=" * 60)
    logger.info(f"📊 РЕЗУЛЬТАТЫ: {success_count}/{total_tests} тестов прошли успешно")
    
    if success_count == total_tests:
        logger.info("✅ Все исправления работают корректно!")
        return True
    else:
        logger.error("❌ Некоторые исправления требуют доработки")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
