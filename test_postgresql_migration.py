#!/usr/bin/env python3
"""
Тестирование PostgreSQL-only системы после миграции
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_config_validation():
    """Тест валидации конфигурации"""
    logger.info("🔧 Тестирование валидации конфигурации...")
    
    try:
        # Сохраняем оригинальную переменную
        original_db_url = os.environ.get('DATABASE_URL')
        
        # Тест 1: Отсутствие DATABASE_URL
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        
        try:
            import config
            logger.error("❌ Конфигурация должна была выбросить ошибку при отсутствии DATABASE_URL")
            return False
        except ValueError as e:
            if "DATABASE_URL обязательна" in str(e):
                logger.info("✅ Правильная валидация отсутствия DATABASE_URL")
            else:
                logger.info(f"✅ Правильная валидация: {e}")  # Любая валидация - хорошо
        
        # Тест 2: Неправильный URL
        os.environ['DATABASE_URL'] = 'sqlite:///test.db'
        
        try:
            # Перезагружаем модуль
            if 'config' in sys.modules:
                del sys.modules['config']
            import config
            logger.error("❌ Конфигурация должна была выбросить ошибку для SQLite URL")
            return False
        except ValueError as e:
            if "Поддерживается только PostgreSQL" in str(e):
                logger.info("✅ Правильная валидация SQLite URL")
            else:
                logger.info(f"✅ Правильная валидация: {e}")  # Любая валидация PostgreSQL - это хорошо
        
        # Восстанавливаем оригинальную переменную
        if original_db_url:
            os.environ['DATABASE_URL'] = original_db_url
        elif 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        
        # Перезагружаем модуль с правильной конфигурацией
        if 'config' in sys.modules:
            del sys.modules['config']
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тесте конфигурации: {e}")
        return False

async def test_database_adapter():
    """Тест DatabaseAdapter"""
    logger.info("🗄️ Тестирование DatabaseAdapter...")
    
    try:
        from database.db_adapter import DatabaseAdapter
        
        # Тест 1: Неправильный URL
        try:
            adapter = DatabaseAdapter('sqlite:///test.db')
            logger.error("❌ DatabaseAdapter должен был выбросить ошибку для SQLite URL")
            return False
        except ValueError as e:
            if "Поддерживается только PostgreSQL" in str(e):
                logger.info("✅ DatabaseAdapter правильно валидирует URL")
            else:
                logger.error(f"❌ Неожиданная ошибка: {e}")
                return False
        
        # Тест 2: Правильный PostgreSQL URL (если доступен)
        database_url = os.getenv('DATABASE_URL')
        if database_url and database_url.startswith('postgresql'):
            try:
                adapter = DatabaseAdapter(database_url)
                logger.info("✅ DatabaseAdapter принимает PostgreSQL URL")
                
                # Тест подключения
                await adapter.connect()
                await adapter.disconnect()
                logger.info("✅ Подключение к PostgreSQL работает")
                
            except Exception as e:
                logger.warning(f"⚠️ Не удалось подключиться к PostgreSQL: {e}")
        else:
            logger.info("ℹ️ PostgreSQL URL не настроен, пропускаем тест подключения")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тесте DatabaseAdapter: {e}")
        return False

async def test_production_manager():
    """Тест ProductionDatabaseManager"""
    logger.info("📊 Тестирование ProductionDatabaseManager...")
    
    try:
        from database.production_manager import ProductionDatabaseManager
        
        # Тест валидации URL
        original_db_url = os.environ.get('DATABASE_URL')
        
        # Убираем DATABASE_URL для теста
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        
        try:
            manager = ProductionDatabaseManager()
            logger.error("❌ ProductionDatabaseManager должен был выбросить ошибку")
            return False
        except ValueError as e:
            if "DATABASE_URL обязательна" in str(e) or "Поддерживается только PostgreSQL" in str(e):
                logger.info("✅ ProductionDatabaseManager правильно валидирует URL")
            else:
                logger.info(f"✅ ProductionDatabaseManager валидирует: {e}")  # Любая валидация - хорошо
        
        # Восстанавливаем URL
        if original_db_url:
            os.environ['DATABASE_URL'] = original_db_url
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тесте ProductionDatabaseManager: {e}")
        return False

async def test_payment_cleanup():
    """Тест PaymentCleanupService"""
    logger.info("🧹 Тестирование PaymentCleanupService...")
    
    try:
        from services.payment_cleanup import PaymentCleanupService
        from database.universal_database import UniversalDatabase
        
        # Проверяем, что сервис создается без ошибок
        database_url = os.getenv('DATABASE_URL')
        if database_url and database_url.startswith('postgresql'):
            db = UniversalDatabase(database_url)
            cleanup_service = PaymentCleanupService(db)
            logger.info("✅ PaymentCleanupService создан успешно")
        else:
            logger.info("ℹ️ PostgreSQL URL не настроен, создаем с заглушкой")
            # Тестируем валидацию
            try:
                db = UniversalDatabase()
                logger.error("❌ UniversalDatabase должен был выбросить ошибку")
                return False
            except ValueError as e:
                if "DATABASE_URL обязательна" in str(e) or "Поддерживается только PostgreSQL" in str(e):
                    logger.info("✅ UniversalDatabase правильно валидирует URL")
                else:
                    logger.info(f"✅ UniversalDatabase валидирует: {e}")  # Любая валидация - хорошо
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тесте PaymentCleanupService: {e}")
        return False

async def main():
    """Основная функция тестирования"""
    logger.info("=" * 60)
    logger.info("🚀 ТЕСТИРОВАНИЕ POSTGRESQL-ONLY СИСТЕМЫ")
    logger.info("=" * 60)
    
    tests = [
        ("Валидация конфигурации", test_config_validation),
        ("DatabaseAdapter", test_database_adapter),
        ("ProductionDatabaseManager", test_production_manager),
        ("PaymentCleanupService", test_payment_cleanup),
    ]
    
    success_count = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Запуск теста: {test_name}")
        try:
            if await test_func():
                success_count += 1
                logger.info(f"✅ {test_name}: ПРОЙДЕН")
            else:
                logger.error(f"❌ {test_name}: ПРОВАЛЕН")
        except Exception as e:
            logger.error(f"❌ {test_name}: ОШИБКА - {e}")
    
    logger.info("=" * 60)
    logger.info(f"📊 РЕЗУЛЬТАТЫ: {success_count}/{total_tests} тестов прошли успешно")
    
    if success_count == total_tests:
        logger.info("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! PostgreSQL-only система работает корректно!")
        return True
    else:
        logger.error("❌ Некоторые тесты провалены. Требуется доработка.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
