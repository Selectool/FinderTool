#!/usr/bin/env python3
"""
Интегрированный запуск бота и админ-панели в одном процессе
"""
import asyncio
import threading
import uvicorn
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Устанавливаем продакшн режим сразу
os.environ["ENVIRONMENT"] = "production"

def run_admin_panel():
    """Запуск админ-панели в отдельном потоке"""
    try:
        from admin.config import HOST, PORT, DEBUG, LOG_LEVEL
        
        print(f"🌐 Запуск админ-панели на {HOST}:{PORT}")
        
        uvicorn.run(
            "admin.app:app",
            host=HOST,
            port=PORT,
            reload=False,  # В продакшн не используем reload
            log_level=LOG_LEVEL.lower(),
            access_log=DEBUG
        )
    except Exception as e:
        print(f"❌ Ошибка запуска админ-панели: {e}")

async def run_telegram_bot():
    """Запуск Telegram бота"""
    try:
        # Импортируем и запускаем основной код бота
        from main import main
        await main()
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")

async def main_integrated():
    """Основная функция для запуска интегрированного сервиса"""
    print("🚀 Запуск интегрированного сервиса...")

    try:
        # Сначала инициализируем production database manager
        print("🗄️ Инициализация production базы данных...")
        from database.production_manager import ProductionDatabaseManager
        from database.db_adapter import set_database, DatabaseAdapter

        # Создаем и инициализируем production manager
        production_manager = ProductionDatabaseManager()
        await production_manager.initialize_database()

        # Создаем адаптер и устанавливаем глобально
        database_url = os.getenv("DATABASE_URL", "sqlite:///bot.db")
        adapter = DatabaseAdapter(database_url)
        await adapter.connect()
        set_database(adapter)
        print("✅ Production база данных инициализирована")

        # Запускаем админ-панель в отдельном потоке
        admin_thread = threading.Thread(target=run_admin_panel, daemon=True)
        admin_thread.start()

        print("✅ Админ-панель запущена в фоновом потоке")

        # Небольшая задержка для инициализации админки
        await asyncio.sleep(3)

        # Запускаем бота в основном потоке
        print("🤖 Запуск Telegram бота...")
        await run_telegram_bot()

    except KeyboardInterrupt:
        print("\n👋 Сервис остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main_integrated())
    except KeyboardInterrupt:
        print("\n👋 Сервис остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
