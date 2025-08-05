#!/usr/bin/env python3
"""
Скрипт для сброса базы данных к чистому состоянию
Исправляет проблему с неправильной статистикой платежей
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from database.reset_manager import DatabaseResetManager
from utils.logging_config import setup_logging

logger = setup_logging()

async def main():
    """Основная функция сброса"""
    print("=" * 60)
    print("🔄 СБРОС БАЗЫ ДАННЫХ К ЧИСТОМУ СОСТОЯНИЮ")
    print("=" * 60)
    print()
    
    # Предупреждение
    print("⚠️  ВНИМАНИЕ!")
    print("   Этот скрипт удалит ВСЕ данные из базы данных:")
    print("   • Всех пользователей (кроме админов)")
    print("   • Все платежи и статистику")
    print("   • Все запросы пользователей")
    print("   • Все сообщения рассылок")
    print()
    
    # Подтверждение
    confirm = input("Вы уверены, что хотите продолжить? (да/нет): ").lower().strip()
    if confirm not in ['да', 'yes', 'y']:
        print("❌ Операция отменена пользователем")
        return
    
    print()
    print("🚀 Начинаем сброс базы данных...")
    
    try:
        # Создаем менеджер сброса
        reset_manager = DatabaseResetManager()
        
        # Выполняем сброс
        success = await reset_manager.reset_to_clean_state(keep_admin_users=True)
        
        if success:
            print("✅ Сброс базы данных выполнен успешно!")
            print()
            
            # Получаем статистику
            stats = await reset_manager.get_reset_statistics()
            
            print("📊 Статистика после сброса:")
            print(f"   • Размер БД: {stats.get('database_size_mb', 0)} MB")
            print(f"   • Таблиц: {stats.get('tables_count', 0)}")
            print(f"   • Пользователей: {stats.get('users_count', 0)}")
            print(f"   • Админов: {stats.get('admin_users_count', 0)}")
            print(f"   • Платежей: {stats.get('payments_count', 0)}")
            print(f"   • Дата сброса: {stats.get('reset_date', 'Неизвестно')}")
            print()
            
            print("🎯 ИСПРАВЛЕНИЯ:")
            print("   ✅ Статистика платежей теперь корректная")
            print("   ✅ Считаются только успешные платежи")
            print("   ✅ Неоплаченные инвойсы не влияют на статистику")
            print()
            
            print("🚀 Следующие шаги:")
            print("   1. Перезапустите бота для применения изменений")
            print("   2. Проверьте работу статистики платежей")
            print("   3. Убедитесь, что админы сохранены")
            
        else:
            print("❌ Ошибка при сбросе базы данных!")
            print("   Проверьте логи для получения подробной информации")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⌨️ Операция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        logger.error(f"Критическая ошибка при сбросе БД: {e}")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("✅ СБРОС ЗАВЕРШЕН УСПЕШНО")
    print("=" * 60)

if __name__ == "__main__":
    # Проверяем Python версию
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    
    # Запускаем сброс
    asyncio.run(main())
