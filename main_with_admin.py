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

def run_telegram_bot():
    """Запуск Telegram бота"""
    try:
        # Импортируем и запускаем основной код бота
        from main import main
        main()
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")

if __name__ == "__main__":
    print("🚀 Запуск интегрированного сервиса...")
    
    # Устанавливаем продакшн режим
    os.environ["ENVIRONMENT"] = "production"
    
    try:
        # Запускаем админ-панель в отдельном потоке
        admin_thread = threading.Thread(target=run_admin_panel, daemon=True)
        admin_thread.start()
        
        print("✅ Админ-панель запущена в фоновом потоке")
        
        # Небольшая задержка для инициализации админки
        import time
        time.sleep(2)
        
        # Запускаем бота в основном потоке
        print("🤖 Запуск Telegram бота...")
        run_telegram_bot()
        
    except KeyboardInterrupt:
        print("\n👋 Сервис остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
