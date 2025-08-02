#!/usr/bin/env python3
"""
Production Startup Script
Главный скрипт для запуска production-ready системы
"""
import subprocess
import sys
import os
import time
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def print_banner():
    """Показать баннер запуска"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           🚀 TELEGRAM CHANNEL FINDER BOT 🚀                 ║
║                                                              ║
║                   PRODUCTION STARTUP                         ║
║                                                              ║
║  🎯 Senior Developer Level Production-Ready System          ║
║  📊 Supervisor Process Management                            ║
║  🔄 Automatic Migrations & Data Sync                        ║
║  💾 Data Persistence & Backup System                        ║
║  🔍 Health Monitoring & Auto-Recovery                       ║
║  🌐 Web Admin Panel with Authentication                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

def show_help():
    """Показать справку"""
    help_text = """
🛠️ PRODUCTION STARTUP COMMANDS:

📋 Основные команды:
  python production_startup.py                  - Полный запуск production системы
  python production_startup.py deploy           - Деплой с миграциями и бэкапом
  python production_startup.py supervisor       - Запуск только Supervisor
  python production_startup.py status           - Статус всех сервисов
  python production_startup.py restart          - Перезапуск всех сервисов
  python production_startup.py stop             - Остановка всех сервисов
  python production_startup.py logs [service]   - Просмотр логов

🔧 Управление миграциями:
  python production_startup.py migrate          - Применить миграции
  python production_startup.py migrate-status   - Статус миграций
  python production_startup.py backup           - Создать бэкап данных

📊 Мониторинг:
  python production_startup.py health           - Проверка состояния системы
  python production_startup.py dashboard        - Информация об админ-панели

🎯 Примеры использования:
  # Полный запуск production системы
  python production_startup.py

  # Деплой новой версии с сохранением данных
  python production_startup.py deploy

  # Проверка статуса всех сервисов
  python production_startup.py status

🌐 После запуска:
  Админ-панель: http://185.207.66.201:8080
  Логин: admin / admin123
"""
    print(help_text)

def main():
    """Основная функция"""
    print_banner()
    
    # Устанавливаем переменные окружения
    os.environ["ENVIRONMENT"] = "production"
    os.environ["PYTHONPATH"] = "/app"
    os.environ["PYTHONUNBUFFERED"] = "1"
    
    # Определяем команду
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    
    if command in ["help", "-h", "--help"]:
        show_help()
        return
    
    logger.info(f"🎯 Выполнение команды: {command}")
    
    try:
        if command == "start" or command == "":
            # Полный запуск production системы
            logger.info("🚀 Запуск полной production системы...")
            subprocess.run([sys.executable, "production_supervisor_manager.py", "start"], check=True)
            
        elif command == "deploy":
            # Деплой с миграциями и бэкапом
            logger.info("📦 Запуск production деплоя...")
            subprocess.run([sys.executable, "production_deploy_manager.py"], check=True)
            
        elif command == "supervisor":
            # Запуск только Supervisor
            logger.info("📊 Запуск Supervisor...")
            subprocess.run([sys.executable, "production_supervisor_manager.py", "start"], check=True)
            
        elif command == "status":
            # Статус сервисов
            logger.info("📋 Проверка статуса сервисов...")
            subprocess.run([sys.executable, "production_supervisor_manager.py", "status"], check=True)
            
        elif command == "restart":
            # Перезапуск сервисов
            logger.info("🔄 Перезапуск всех сервисов...")
            subprocess.run([sys.executable, "production_supervisor_manager.py", "restart"], check=True)
            
        elif command == "stop":
            # Остановка сервисов
            logger.info("🛑 Остановка всех сервисов...")
            subprocess.run([sys.executable, "production_supervisor_manager.py", "stop"], check=True)
            
        elif command == "logs":
            # Просмотр логов
            service = sys.argv[2] if len(sys.argv) > 2 else None
            if service:
                logger.info(f"📄 Просмотр логов сервиса: {service}")
                subprocess.run([sys.executable, "production_supervisor_manager.py", "logs", service], check=True)
            else:
                logger.info("📄 Просмотр логов всех сервисов...")
                subprocess.run([sys.executable, "production_supervisor_manager.py", "logs"], check=True)
                
        elif command == "migrate":
            # Применить миграции
            logger.info("🔧 Применение миграций...")
            subprocess.run([sys.executable, "manage_migrations.py", "migrate"], check=True)
            
        elif command == "migrate-status":
            # Статус миграций
            logger.info("📊 Статус миграций...")
            subprocess.run([sys.executable, "manage_migrations.py", "status"], check=True)
            
        elif command == "backup":
            # Создать бэкап
            logger.info("📦 Создание бэкапа...")
            subprocess.run([sys.executable, "-c", """
import asyncio
from production_data_sync import ProductionDataSync
async def main():
    sync = ProductionDataSync()
    await sync.create_data_backup()
asyncio.run(main())
"""], check=True)
            
        elif command == "health":
            # Проверка состояния
            logger.info("🔍 Проверка состояния системы...")
            subprocess.run([sys.executable, "-c", """
import asyncio
from production_health_monitor import ProductionHealthMonitor
async def main():
    monitor = ProductionHealthMonitor()
    report = await monitor.perform_health_check()
    print(f"Общий статус: {report['overall_status']}")
asyncio.run(main())
"""], check=True)
            
        elif command == "dashboard":
            # Информация об админ-панели
            logger.info("🌐 Админ-панель доступна по адресу:")
            logger.info("   http://185.207.66.201:8080")
            logger.info("   Логин: admin")
            logger.info("   Пароль: admin123")
            
        else:
            logger.error(f"❌ Неизвестная команда: {command}")
            logger.info("💡 Используйте 'python production_startup.py help' для справки")
            sys.exit(1)
            
        logger.info("✅ Команда выполнена успешно")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Ошибка выполнения команды: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("👋 Операция прервана пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
