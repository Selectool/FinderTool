#!/usr/bin/env python3
"""
Скрипт инициализации production-ready базы данных
"""
import asyncio
import sys
import os
import logging
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from database.production_manager import ProductionDatabaseManager
from database.backup_system import BackupSystem
from database.monitoring import DatabaseMonitor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def init_production_database():
    """Инициализация production-ready базы данных"""
    print("🚀 ИНИЦИАЛИЗАЦИЯ PRODUCTION-READY БАЗЫ ДАННЫХ")
    print("=" * 60)
    
    # Проверяем существование основной базы
    db_path = "bot.db"
    if not os.path.exists(db_path):
        print(f"❌ Основная база данных {db_path} не найдена!")
        print("   Создайте базу данных или запустите основной бот сначала.")
        return False
    
    try:
        # 1. Инициализируем менеджер базы данных
        print("\n📊 Инициализация менеджера базы данных...")
        db_manager = ProductionDatabaseManager(db_path)
        
        # 2. Создаем бэкап перед оптимизацией
        print("\n💾 Создание бэкапа перед оптимизацией...")
        backup_system = BackupSystem(db_path)
        backup_path = await backup_system.create_backup("pre_production_init")
        
        if backup_path:
            print(f"✅ Бэкап создан: {backup_path}")
        else:
            print("❌ Ошибка создания бэкапа!")
            return False
        
        # 3. Проверяем здоровье базы данных
        print("\n🔍 Проверка здоровья базы данных...")
        health = await db_manager.health_check()
        
        if health['status'] == 'healthy':
            print("✅ База данных здорова")
            for check, status in health['checks'].items():
                print(f"   • {check}: {status}")
        else:
            print(f"❌ Проблемы с базой данных: {health.get('error', 'Unknown')}")
            return False
        
        # 4. Создаем индексы для производительности
        print("\n⚡ Создание индексов для оптимизации...")
        await db_manager.create_indexes()
        print("✅ Индексы созданы")
        
        # 5. Анализируем и оптимизируем базу данных
        print("\n🔧 Анализ и оптимизация базы данных...")
        await db_manager.analyze_database()
        print("✅ Оптимизация завершена")
        
        # 6. Получаем статистику
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
        
        # 7. Настраиваем систему мониторинга
        print("\n📡 Настройка системы мониторинга...")
        monitor = DatabaseMonitor(db_path)
        metrics = await monitor.collect_metrics()
        print(f"✅ Мониторинг настроен (текущие метрики собраны)")
        
        # 8. Настраиваем автоматические бэкапы
        print("\n⏰ Настройка автоматических бэкапов...")
        backup_system.start_scheduler()
        print("✅ Планировщик бэкапов запущен")
        print("   • Ежедневные бэкапы: 02:00")
        print("   • Еженедельные бэкапы: Воскресенье 03:00")
        print("   • Ежемесячные бэкапы: 1 число 04:00")
        print("   • Очистка старых бэкапов: 05:00")
        
        # 9. Создаем отчет
        print("\n📋 Генерация отчета...")
        report = await monitor.generate_report()
        
        if 'error' not in report:
            print(f"✅ Отчет сгенерирован")
            print(f"   • Статус: {report['health_status']}")
            print(f"   • Алертов: {len(report['alerts'])}")
            
            if report['alerts']:
                print("⚠️  Обнаружены алерты:")
                for alert in report['alerts']:
                    print(f"   • {alert['type']}: {alert['message']}")
        
        # 10. Очищаем дублированные базы данных
        print("\n🧹 Очистка дублированных баз данных...")
        duplicate_dbs = ['bot_dev.db', 'admin/bot.db']
        
        for db_file in duplicate_dbs:
            if os.path.exists(db_file):
                try:
                    # Создаем бэкап перед удалением
                    backup_name = f"backup_before_cleanup_{os.path.basename(db_file)}"
                    backup_path = f"backups/{backup_name}"
                    os.makedirs("backups", exist_ok=True)
                    
                    import shutil
                    shutil.copy2(db_file, backup_path)
                    
                    # Удаляем дублированную базу
                    os.remove(db_file)
                    print(f"✅ Удалена дублированная база: {db_file} (бэкап: {backup_path})")
                    
                except Exception as e:
                    print(f"⚠️  Не удалось удалить {db_file}: {e}")
        
        print("\n" + "=" * 60)
        print("🎉 ИНИЦИАЛИЗАЦИЯ PRODUCTION-READY БАЗЫ ДАННЫХ ЗАВЕРШЕНА!")
        print("=" * 60)
        
        print("\n📋 ИТОГИ:")
        print("✅ База данных оптимизирована для продакшн")
        print("✅ Индексы созданы для быстрой работы")
        print("✅ Система бэкапов настроена")
        print("✅ Мониторинг производительности активен")
        print("✅ Дублированные базы очищены")
        
        print("\n💡 РЕКОМЕНДАЦИИ:")
        print("• Регулярно проверяйте логи мониторинга")
        print("• Следите за размером базы данных")
        print("• Проверяйте успешность автоматических бэкапов")
        print("• При проблемах используйте health check")
        
        print("\n🔧 ПОЛЕЗНЫЕ КОМАНДЫ:")
        print("• Проверка здоровья: python -c \"from database.production_manager import db_manager; import asyncio; print(asyncio.run(db_manager.health_check()))\"")
        print("• Создание бэкапа: python -c \"from database.backup_system import backup_system; import asyncio; print(asyncio.run(backup_system.create_backup()))\"")
        print("• Отчет мониторинга: python -c \"from database.monitoring import db_monitor; import asyncio; print(asyncio.run(db_monitor.generate_report()))\"")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}")
        print(f"\n❌ ОШИБКА ИНИЦИАЛИЗАЦИИ: {e}")
        return False


async def main():
    """Главная функция"""
    success = await init_production_database()
    
    if success:
        print("\n🚀 База данных готова к продакшн использованию!")
        sys.exit(0)
    else:
        print("\n💥 Инициализация не удалась!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
