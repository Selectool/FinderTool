#!/usr/bin/env python3
"""
Dokploy Production Launcher
Единый скрипт для запуска Telegram бота + FastAPI админ-панели
Оптимизирован для Railpack/Dokploy deployment
"""

import asyncio
import logging
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class DokployLauncher:
    """Launcher для Dokploy с поддержкой единого и раздельного запуска"""
    
    def __init__(self):
        self.running = True
        self.bot_process = None
        self.admin_process = None
        
        # Проверяем переменные окружения
        self._check_environment()
    
    def _check_environment(self):
        """Проверка критически важных переменных окружения"""
        required_vars = ['BOT_TOKEN']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
            sys.exit(1)
        
        logger.info("✅ Переменные окружения проверены")
        
        # Логируем конфигурацию
        logger.info("🔧 Конфигурация:")
        logger.info(f"  - BOT_TOKEN: {'✅ Установлен' if os.getenv('BOT_TOKEN') else '❌ Отсутствует'}")
        logger.info(f"  - DATABASE_URL: {'✅ PostgreSQL' if os.getenv('DATABASE_URL') else '⚠️ SQLite'}")
        logger.info(f"  - ADMIN_HOST: {os.getenv('ADMIN_HOST', '0.0.0.0')}")
        logger.info(f"  - ADMIN_PORT: {os.getenv('ADMIN_PORT', '8080')}")
        logger.info(f"  - ENVIRONMENT: {os.getenv('ENVIRONMENT', 'development')}")
    
    def start_telegram_bot(self):
        """Запуск Telegram бота"""
        try:
            logger.info("🤖 Запуск Telegram бота...")
            
            # Импортируем и запускаем main.py
            import main
            asyncio.run(main.main())
            
        except Exception as e:
            logger.error(f"❌ Ошибка в Telegram боте: {e}")
            self.running = False
    
    def start_admin_panel(self):
        """Запуск FastAPI админ-панели"""
        try:
            logger.info("🌐 Запуск FastAPI админ-панели...")
            
            # Импортируем и запускаем run_admin.py
            import run_admin
            run_admin.main()
            
        except Exception as e:
            logger.error(f"❌ Ошибка в админ-панели: {e}")
            self.running = False
    
    def start_unified_app(self):
        """Запуск единого приложения app.py"""
        try:
            logger.info("🚀 Запуск единого приложения...")
            
            if os.path.exists('app.py'):
                # Запускаем app.py напрямую
                import uvicorn
                
                host = os.getenv('ADMIN_HOST', '0.0.0.0')
                port = int(os.getenv('ADMIN_PORT', 8080))
                
                logger.info(f"🌐 Запуск на {host}:{port}")
                
                uvicorn.run(
                    "app:app",
                    host=host,
                    port=port,
                    reload=False,
                    access_log=True,
                    log_level="info"
                )
            else:
                logger.warning("⚠️ app.py не найден, запускаем раздельные процессы")
                self.start_separate_processes()
                
        except Exception as e:
            logger.error(f"❌ Ошибка в едином приложении: {e}")
            logger.info("🔄 Переключаемся на раздельные процессы...")
            self.start_separate_processes()
    
    def start_separate_processes(self):
        """Запуск раздельных процессов main.py + run_admin.py"""
        logger.info("🔄 Запуск раздельных процессов...")
        
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Запускаем Telegram бота
                logger.info("🤖 Запуск Telegram бота в отдельном потоке...")
                bot_future = executor.submit(self.start_telegram_bot)
                
                # Небольшая задержка
                time.sleep(3)
                
                # Запускаем админ-панель
                logger.info("🌐 Запуск админ-панели в отдельном потоке...")
                admin_future = executor.submit(self.start_admin_panel)
                
                # Ждем завершения любого из процессов
                while self.running:
                    if bot_future.done():
                        if bot_future.exception():
                            logger.error(f"❌ Telegram бот завершился с ошибкой: {bot_future.exception()}")
                        else:
                            logger.info("✅ Telegram бот завершился")
                        break
                    
                    if admin_future.done():
                        if admin_future.exception():
                            logger.error(f"❌ Админ-панель завершилась с ошибкой: {admin_future.exception()}")
                        else:
                            logger.info("✅ Админ-панель завершилась")
                        break
                    
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки...")
            self.running = False
    
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"🛑 Получен сигнал {signum}, завершаем работу...")
        self.running = False
        sys.exit(0)
    
    def run(self):
        """Основной метод запуска"""
        logger.info("=" * 60)
        logger.info("🚀 DOKPLOY LAUNCHER - Telegram Channel Finder Bot")
        logger.info("🏗️  Платформа: Railpack/Dokploy")
        logger.info("🗄️  База данных: PostgreSQL")
        logger.info("=" * 60)
        
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            # Определяем режим запуска
            launch_mode = os.getenv('LAUNCH_MODE', 'unified')
            
            logger.info(f"🎯 Режим запуска: {launch_mode}")
            
            if launch_mode == 'unified':
                # Пытаемся запустить единое приложение
                self.start_unified_app()
            elif launch_mode == 'separate':
                # Запускаем раздельные процессы
                self.start_separate_processes()
            else:
                # Автоопределение - сначала пытаемся единое, потом раздельное
                self.start_unified_app()
                
        except KeyboardInterrupt:
            logger.info("🛑 Остановка по запросу пользователя")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            sys.exit(1)
        finally:
            logger.info("✅ Dokploy launcher завершен")

def main():
    """Точка входа"""
    
    # Проверяем Python версию
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    
    # Показываем информацию о запуске
    print(f"🐍 Python: {sys.version}")
    print(f"📁 Рабочая директория: {os.getcwd()}")
    print(f"🌍 Окружение: {os.getenv('ENVIRONMENT', 'production')}")
    
    # Создаем и запускаем launcher
    launcher = DokployLauncher()
    launcher.run()

if __name__ == "__main__":
    main()
