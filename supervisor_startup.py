#!/usr/bin/env python3
"""
Supervisor-based Startup Script для Telegram Channel Finder Bot
Использует supervisor для управления Telegram ботом и админ-панелью
Оптимизирован для Railpack deployment
"""

import asyncio
import logging
import os
import sys
import subprocess
import time
import signal
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/supervisor_startup.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)


class SupervisorManager:
    """Менеджер для запуска сервисов через supervisor"""
    
    def __init__(self):
        self.supervisor_process = None
        self.running = False
        
        # Создаем директории
        Path("logs").mkdir(exist_ok=True)
        
        # Настройка обработчиков сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"🛑 Получен сигнал {signum}, начинаем graceful shutdown...")
        self.running = False
        if self.supervisor_process:
            self.supervisor_process.terminate()
    
    async def init_database(self):
        """Инициализация базы данных"""
        try:
            logger.info("🔄 Инициализация базы данных...")
            from database.production_manager import init_production_database, db_manager
            from database.db_adapter import set_database
            
            await init_production_database()
            set_database(db_manager)
            logger.info("✅ База данных инициализирована")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            return False
    
    def create_supervisor_config(self):
        """Создание конфигурации supervisor"""
        config_content = """
[supervisord]
nodaemon=true
user=app
logfile=/app/logs/supervisord.log
pidfile=/app/logs/supervisord.pid
childlogdir=/app/logs

[program:telegram-bot]
command=python -c "import asyncio; from bot.main import main; asyncio.run(main())"
directory=/app
user=app
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/app/logs/telegram-bot.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
environment=PYTHONPATH="/app",PYTHONUNBUFFERED="1"

[program:admin-panel]
command=python run_admin.py
directory=/app
user=app
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/app/logs/admin-panel.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
environment=PYTHONPATH="/app",PYTHONUNBUFFERED="1"

[group:findertool]
programs=telegram-bot,admin-panel
priority=999
"""
        
        config_path = Path("/app/supervisord.conf")
        config_path.write_text(config_content.strip())
        logger.info("✅ Конфигурация supervisor создана")
        return config_path
    
    def start_supervisor(self):
        """Запуск supervisor"""
        try:
            config_path = self.create_supervisor_config()
            
            logger.info("🚀 Запуск supervisor...")
            
            # Запускаем supervisor
            self.supervisor_process = subprocess.Popen(
                ["supervisord", "-c", str(config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            logger.info("✅ Supervisor запущен")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска supervisor: {e}")
            return False
    
    def monitor_services(self):
        """Мониторинг сервисов"""
        while self.running:
            try:
                # Проверяем статус supervisor
                if self.supervisor_process and self.supervisor_process.poll() is not None:
                    logger.error("❌ Supervisor остановился")
                    break
                
                # Проверяем здоровье сервисов
                try:
                    import requests
                    admin_response = requests.get('http://localhost:8080/api/health', timeout=5)
                    admin_healthy = admin_response.status_code == 200
                    
                    if admin_healthy:
                        logger.debug("💚 Админ-панель здорова")
                    else:
                        logger.warning("⚠️ Проблемы с админ-панелью")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось проверить админ-панель: {e}")
                
                time.sleep(30)  # Проверяем каждые 30 секунд
                
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга: {e}")
                time.sleep(30)
    
    async def run(self):
        """Главный метод запуска"""
        logger.info("🚀 Запуск Supervisor-based Telegram Channel Finder Bot Service")
        logger.info(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'unknown')}")
        logger.info(f"📍 Database: {os.getenv('DATABASE_URL', 'unknown')[:50]}...")
        
        self.running = True
        
        # 1. Инициализация базы данных
        if not await self.init_database():
            logger.error("💥 Не удалось инициализировать базу данных")
            sys.exit(1)
        
        # 2. Запуск supervisor
        if not self.start_supervisor():
            logger.error("💥 Не удалось запустить supervisor")
            sys.exit(1)
        
        # Ждем запуска сервисов
        await asyncio.sleep(10)
        
        logger.info("🎉 Все сервисы запущены через supervisor!")
        logger.info("📱 Telegram бот: Управляется supervisor")
        logger.info("🌐 Админ-панель: http://localhost:8080")
        logger.info("📊 Supervisor: Мониторинг активен")
        
        try:
            # Мониторинг в отдельном потоке
            import threading
            monitor_thread = threading.Thread(target=self.monitor_services, daemon=True)
            monitor_thread.start()
            
            # Ждем завершения supervisor
            while self.running and self.supervisor_process:
                if self.supervisor_process.poll() is not None:
                    logger.error("❌ Supervisor завершился")
                    break
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки")
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
        finally:
            logger.info("🔄 Завершение работы supervisor сервиса...")
            self.running = False
            
            # Останавливаем supervisor
            if self.supervisor_process and self.supervisor_process.poll() is None:
                logger.info("🛑 Остановка supervisor...")
                self.supervisor_process.terminate()
                
                # Ждем graceful shutdown
                try:
                    self.supervisor_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning("⚠️ Принудительная остановка supervisor...")
                    self.supervisor_process.kill()
            
            logger.info("✅ Supervisor сервис остановлен")


async def main():
    """Главная функция"""
    manager = SupervisorManager()
    await manager.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Прерывание пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)
