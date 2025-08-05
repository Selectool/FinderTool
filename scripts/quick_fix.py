#!/usr/bin/env python3
"""
Быстрое применение исправлений статистики
Простой Python скрипт для применения на сервере
"""
import asyncio
import os
import sys
import subprocess
import time
from pathlib import Path

def log(message, level="INFO"):
    """Логирование с цветами"""
    colors = {
        "INFO": "\033[0;34m",
        "SUCCESS": "\033[0;32m", 
        "WARNING": "\033[1;33m",
        "ERROR": "\033[0;31m"
    }
    reset = "\033[0m"
    print(f"{colors.get(level, '')}{message}{reset}")

def run_command(command, check=True):
    """Выполнить команду в shell"""
    log(f"Выполняю: {command}")
    try:
        result = subprocess.run(command, shell=True, check=check, 
                              capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        log(f"Ошибка команды: {e}", "ERROR")
        if e.stderr:
            print(e.stderr)
        return False

def stop_processes():
    """Остановить все процессы бота"""
    log("Остановка процессов...")
    
    # Останавливаем Python процессы
    run_command("pkill -f 'python main.py'", check=False)
    run_command("pkill -f 'python run_admin.py'", check=False)
    
    time.sleep(3)
    log("Процессы остановлены", "SUCCESS")

def check_database():
    """Проверить подключение к базе данных"""
    log("Проверка базы данных...")
    
    # Устанавливаем DATABASE_URL если не установлена
    if not os.getenv('DATABASE_URL'):
        os.environ['DATABASE_URL'] = "postgresql://findertool_user:Findertool1999!@postgres:5432/findertool_prod"
        log("DATABASE_URL установлена")
    
    # Проверяем подключение
    test_code = """
import asyncio
import asyncpg
import os

async def test():
    try:
        conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
        await conn.execute('SELECT 1')
        await conn.close()
        print('✅ PostgreSQL OK')
        return True
    except Exception as e:
        print(f'❌ PostgreSQL Error: {e}')
        return False

result = asyncio.run(test())
exit(0 if result else 1)
"""
    
    with open('/tmp/test_db.py', 'w') as f:
        f.write(test_code)
    
    if run_command("python /tmp/test_db.py"):
        log("База данных доступна", "SUCCESS")
        return True
    else:
        log("Ошибка подключения к базе данных", "ERROR")
        return False

def migrate_sqlite_if_needed():
    """Мигрировать данные из SQLite если нужно"""
    if os.path.exists('bot.db'):
        log("Найден SQLite файл", "WARNING")
        
        response = input("Мигрировать данные из SQLite в PostgreSQL? (y/N): ")
        if response.lower() == 'y':
            log("Запуск миграции...")
            
            if os.path.exists('scripts/migrate_sqlite_to_postgresql.py'):
                success = run_command(
                    "python scripts/migrate_sqlite_to_postgresql.py "
                    "--sqlite-path bot.db --dry-run"
                )
                
                if success:
                    confirm = input("Dry run успешен. Выполнить реальную миграцию? (y/N): ")
                    if confirm.lower() == 'y':
                        run_command(
                            "python scripts/migrate_sqlite_to_postgresql.py "
                            "--sqlite-path bot.db"
                        )
                        
                        # Переименовываем SQLite файл
                        backup_name = f"bot.db.backup_{int(time.time())}"
                        os.rename('bot.db', backup_name)
                        log(f"SQLite файл переименован в {backup_name}", "SUCCESS")
            else:
                log("Скрипт миграции не найден", "ERROR")

def test_statistics():
    """Тестировать систему статистики"""
    log("Тестирование системы статистики...")
    
    test_code = """
import asyncio
import os
import sys

async def test():
    try:
        from database.universal_database import UniversalDatabase
        from services.statistics_service import StatisticsService
        
        db = UniversalDatabase(os.getenv('DATABASE_URL'))
        stats_service = StatisticsService(db)
        
        # Тест базовой статистики
        basic_stats = await stats_service.get_basic_statistics()
        print(f'✅ Пользователей: {basic_stats.total_users}')
        
        # Тест детальной статистики  
        detailed_stats = await stats_service.get_detailed_statistics()
        print(f'✅ Метрик: {len(detailed_stats)}')
        
        # Тест статистики платежей
        payment_stats = await stats_service.get_payment_statistics()
        print(f'✅ Платежей: {payment_stats.get("total", {}).get("count", 0)}')
        
        print('✅ Все тесты пройдены')
        return True
        
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        return False

result = asyncio.run(test())
exit(0 if result else 1)
"""
    
    with open('/tmp/test_stats.py', 'w') as f:
        f.write(test_code)
    
    if run_command("python /tmp/test_stats.py"):
        log("Система статистики работает", "SUCCESS")
        return True
    else:
        log("Ошибка системы статистики", "ERROR")
        return False

def start_services():
    """Запустить сервисы"""
    log("Запуск сервисов...")
    
    # Запускаем бота
    log("Запуск бота...")
    run_command("nohup python main.py > bot.log 2>&1 &")
    
    time.sleep(5)
    
    # Проверяем запуск бота
    if run_command("pgrep -f 'python main.py'", check=False):
        log("✅ Бот запущен", "SUCCESS")
    else:
        log("❌ Бот не запустился", "ERROR")
        return False
    
    # Запускаем админ-панель
    log("Запуск админ-панели...")
    run_command("nohup python run_admin.py > admin.log 2>&1 &")
    
    time.sleep(3)
    
    # Проверяем запуск админ-панели
    if run_command("pgrep -f 'python run_admin.py'", check=False):
        log("✅ Админ-панель запущена", "SUCCESS")
    else:
        log("⚠️ Админ-панель не запустилась", "WARNING")
    
    return True

def main():
    """Основная функция"""
    print("🚀 Быстрое применение исправлений статистики")
    print("=" * 50)
    
    # Проверяем, что мы в правильной директории
    if not os.path.exists('main.py'):
        log("Файл main.py не найден! Перейдите в директорию проекта.", "ERROR")
        sys.exit(1)
    
    # Активируем виртуальное окружение
    if os.path.exists('.venv/bin/activate'):
        log("Активация виртуального окружения...")
        # Для Linux
        venv_python = '.venv/bin/python'
    elif os.path.exists('.venv/Scripts/activate'):
        # Для Windows (если запускаем локально)
        venv_python = '.venv/Scripts/python'
    else:
        log("Виртуальное окружение не найдено", "ERROR")
        sys.exit(1)
    
    # Обновляем sys.executable для использования venv
    sys.executable = venv_python
    
    try:
        # Выполняем все этапы
        stop_processes()
        
        if not check_database():
            log("Критическая ошибка: база данных недоступна", "ERROR")
            sys.exit(1)
        
        migrate_sqlite_if_needed()
        
        # Устанавливаем зависимости
        log("Установка зависимостей...")
        run_command(f"{venv_python} -m pip install -r requirements.txt")
        
        if not test_statistics():
            log("Критическая ошибка: система статистики не работает", "ERROR")
            sys.exit(1)
        
        if not start_services():
            log("Ошибка запуска сервисов", "ERROR")
            sys.exit(1)
        
        # Финальная проверка
        log("Финальная проверка...")
        time.sleep(5)
        
        print("\n" + "=" * 50)
        log("🎉 Исправления применены успешно!", "SUCCESS")
        print("\n📊 Проверьте статистику:")
        print("• Веб-панель: http://185.207.66.201:8080/")
        print("• Команды бота: /stats, /payment_stats, /health")
        print("\n📋 Логи:")
        print("• Бот: tail -f bot.log")
        print("• Админ-панель: tail -f admin.log")
        
    except KeyboardInterrupt:
        log("Прервано пользователем", "WARNING")
        sys.exit(1)
    except Exception as e:
        log(f"Критическая ошибка: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
