#!/usr/bin/env python3
"""
Упрощенная инициализация production-ready базы данных
"""
import asyncio
import sys
import os
import logging
import shutil
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from database.production_manager import ProductionDatabaseManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def simple_init():
    """Упрощенная инициализация"""
    print("🚀 ИНИЦИАЛИЗАЦИЯ PRODUCTION-READY БАЗЫ ДАННЫХ")
    print("=" * 60)
    
    # Проверяем существование основной базы
    db_path = "bot.db"
    if not os.path.exists(db_path):
        print(f"❌ Основная база данных {db_path} не найдена!")
        return False
    
    try:
        # 1. Создаем простой бэкап
        print("\n💾 Создание бэкапа...")
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"bot_backup_init_{timestamp}.db"
        
        shutil.copy2(db_path, backup_path)
        print(f"✅ Бэкап создан: {backup_path}")
        
        # 2. Инициализируем менеджер
        print("\n📊 Инициализация менеджера базы данных...")
        db_manager = ProductionDatabaseManager(db_path)
        
        # 3. Создаем индексы
        print("\n⚡ Создание индексов для оптимизации...")
        await db_manager.create_indexes()
        print("✅ Индексы созданы")
        
        # 4. Анализируем базу данных
        print("\n🔧 Анализ и оптимизация базы данных...")
        await db_manager.analyze_database()
        print("✅ Оптимизация завершена")
        
        # 5. Получаем статистику
        print("\n📈 Сбор статистики базы данных...")
        stats = await db_manager.get_database_stats()
        
        print("📊 Статистика базы данных:")
        print(f"   • Размер файла: {stats['file_size']:,} байт ({stats['file_size']/1024/1024:.1f} MB)")
        print(f"   • Пользователей: {stats.get('users_count', 0)}")
        print(f"   • Запросов: {stats.get('requests_count', 0)}")
        print(f"   • Платежей: {stats.get('payments_count', 0)}")
        print(f"   • Рассылок: {stats.get('broadcasts_count', 0)}")
        print(f"   • Админ пользователей: {stats.get('admin_users_count', 0)}")
        
        if 'users_total' in stats:
            print(f"   • Всего пользователей: {stats['users_total']}")
            print(f"   • С подпиской: {stats['users_subscribed']}")
            print(f"   • Заблокированных: {stats['users_blocked']}")
        
        # 6. Очищаем дублированные базы данных
        print("\n🧹 Очистка дублированных баз данных...")
        duplicate_dbs = ['bot_dev.db', 'admin/bot.db']
        
        for db_file in duplicate_dbs:
            if os.path.exists(db_file):
                try:
                    # Создаем бэкап перед удалением
                    backup_name = f"backup_cleanup_{os.path.basename(db_file)}_{timestamp}"
                    backup_cleanup_path = backup_dir / backup_name
                    
                    shutil.copy2(db_file, backup_cleanup_path)
                    
                    # Удаляем дублированную базу
                    os.remove(db_file)
                    print(f"✅ Удалена дублированная база: {db_file} (бэкап: {backup_cleanup_path})")
                    
                except Exception as e:
                    print(f"⚠️  Не удалось удалить {db_file}: {e}")
        
        print("\n" + "=" * 60)
        print("🎉 ИНИЦИАЛИЗАЦИЯ ЗАВЕРШЕНА!")
        print("=" * 60)
        
        print("\n📋 ИТОГИ:")
        print("✅ База данных оптимизирована для продакшн")
        print("✅ Индексы созданы для быстрой работы")
        print("✅ Дублированные базы очищены")
        print("✅ Бэкапы созданы")
        
        print("\n💡 СЛЕДУЮЩИЕ ШАГИ:")
        print("• Настройте автоматические бэкапы")
        print("• Настройте мониторинг производительности")
        print("• Регулярно проверяйте размер базы данных")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}")
        print(f"\n❌ ОШИБКА ИНИЦИАЛИЗАЦИИ: {e}")
        return False


async def main():
    """Главная функция"""
    success = await simple_init()
    
    if success:
        print("\n🚀 База данных готова к продакшн использованию!")
        sys.exit(0)
    else:
        print("\n💥 Инициализация не удалась!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
