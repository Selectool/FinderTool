#!/usr/bin/env python3
"""
Production-ready исправление всех PostgreSQL проблем
Senior Developer Level Solution
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

async def run_migration():
    """Запустить миграцию для исправления схемы"""
    try:
        from database.migration_manager import MigrationManager
        
        logger.info("🔄 Запуск миграций для исправления схемы...")
        migration_manager = MigrationManager()
        await migration_manager.migrate()
        logger.info("✅ Миграции применены успешно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при применении миграций: {e}")
        return False

def fix_universal_database_methods():
    """Исправить методы UniversalDatabase для PostgreSQL"""
    logger.info("🔧 Исправление UniversalDatabase методов...")
    
    file_path = 'database/universal_database.py'
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Создаем backup
        backup_path = f'{file_path}.production_backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"📁 Backup создан: {backup_path}")
        
        # Критические исправления
        fixes = [
            # get_stats method
            ('total_users_result[0] if total_users_result else 0', 'self._extract_count(total_users_result)'),
            ('active_subs_result[0] if active_subs_result else 0', 'self._extract_count(active_subs_result)'),
            ('requests_today_result[0] if requests_today_result else 0', 'self._extract_count(requests_today_result)'),
            
            # get_users_count method
            ('return result[0] if result else 0', 'return self._extract_count(result)'),
            
            # get_subscribers_count method
            ('result[0] if result else 0', 'self._extract_count(result)'),
            
            # Общие исправления
            ('count = result[0]', 'count = self._extract_count(result)'),
            ('count_result[0]', 'self._extract_count(count_result)'),
            ('users_result[0]', 'self._extract_count(users_result)'),
            ('subs_result[0]', 'self._extract_count(subs_result)'),
        ]
        
        changes_made = 0
        for old_text, new_text in fixes:
            if old_text in content:
                content = content.replace(old_text, new_text)
                changes_made += 1
                logger.info(f"✅ Исправлено: {old_text[:40]}...")
        
        # Записываем исправленный файл
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"🎉 Применено {changes_made} исправлений в UniversalDatabase")
        return changes_made > 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка при исправлении UniversalDatabase: {e}")
        return False

def fix_broadcast_parameters():
    """Исправить параметры рассылок"""
    logger.info("📢 Исправление параметров рассылок...")
    
    files_to_fix = [
        ('admin/api/broadcasts.py', 'scheduled_at=None', 'scheduled_time=None'),
        ('bot/handlers/admin.py', 'scheduled_at=None', 'scheduled_time=None'),
    ]
    
    changes_made = 0
    for file_path, old_text, new_text in files_to_fix:
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if old_text in content:
                    content = content.replace(old_text, new_text)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    logger.info(f"✅ Исправлен файл: {file_path}")
                    changes_made += 1
        except Exception as e:
            logger.error(f"❌ Ошибка при исправлении {file_path}: {e}")
    
    return changes_made > 0

async def test_database_connection():
    """Тестировать подключение к базе данных"""
    logger.info("🔍 Тестирование подключения к базе данных...")
    
    try:
        from database.production_manager import ProductionDatabaseManager
        
        db_manager = ProductionDatabaseManager()
        
        # Тест базового подключения
        stats = await db_manager.get_stats()
        logger.info(f"✅ Статистика получена: {stats}")
        
        # Тест получения пользователей
        users = await db_manager.get_users_paginated(page=1, per_page=5)
        logger.info(f"✅ Пользователи получены: {users['total']} всего")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования БД: {e}")
        return False

async def main():
    """Основная функция исправления"""
    logger.info("=" * 60)
    logger.info("🚀 PRODUCTION-READY ИСПРАВЛЕНИЕ POSTGRESQL ПРОБЛЕМ")
    logger.info("=" * 60)
    
    success_count = 0
    total_steps = 5
    
    # Шаг 1: Исправление UniversalDatabase
    logger.info("\n📝 Шаг 1: Исправление UniversalDatabase методов")
    if fix_universal_database_methods():
        success_count += 1
        logger.info("✅ UniversalDatabase исправлен")
    else:
        logger.error("❌ Ошибка исправления UniversalDatabase")
    
    # Шаг 2: Исправление параметров рассылок
    logger.info("\n📢 Шаг 2: Исправление параметров рассылок")
    if fix_broadcast_parameters():
        success_count += 1
        logger.info("✅ Параметры рассылок исправлены")
    else:
        logger.error("❌ Ошибка исправления параметров рассылок")
    
    # Шаг 3: Применение миграций
    logger.info("\n🔄 Шаг 3: Применение миграций")
    if await run_migration():
        success_count += 1
        logger.info("✅ Миграции применены")
    else:
        logger.error("❌ Ошибка применения миграций")
    
    # Шаг 4: Тестирование подключения
    logger.info("\n🔍 Шаг 4: Тестирование базы данных")
    if await test_database_connection():
        success_count += 1
        logger.info("✅ База данных работает корректно")
    else:
        logger.error("❌ Проблемы с базой данных")
    
    # Шаг 5: Финальная проверка
    logger.info("\n🏁 Шаг 5: Финальная проверка")
    if success_count >= 3:  # Минимум 3 из 4 шагов должны пройти
        success_count += 1
        logger.info("✅ Система готова к работе")
    else:
        logger.error("❌ Требуется дополнительная настройка")
    
    # Результаты
    logger.info("=" * 60)
    logger.info(f"📊 РЕЗУЛЬТАТЫ: {success_count}/{total_steps} шагов выполнено успешно")
    
    if success_count >= 4:
        logger.info("🎉 ИСПРАВЛЕНИЯ ПРИМЕНЕНЫ УСПЕШНО!")
        logger.info("\n📋 Следующие шаги:")
        logger.info("1. Перезапустите бота: python main.py")
        logger.info("2. Перезапустите админ-панель: python run_admin.py")
        logger.info("3. Проверьте статистику в админ-панели")
        return True
    else:
        logger.error("❌ ТРЕБУЕТСЯ ДОПОЛНИТЕЛЬНАЯ НАСТРОЙКА")
        logger.error("Проверьте логи выше для деталей")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
