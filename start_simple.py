#!/usr/bin/env python3
"""
Простой скрипт запуска бота и админ-панели для production
"""
import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# Устанавливаем продакшн режим
os.environ["ENVIRONMENT"] = "production"

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    print(f"\n🛑 Получен сигнал {signum}, останавливаем сервисы...")
    
    # Останавливаем процессы
    try:
        if 'bot_process' in globals() and bot_process.poll() is None:
            print("🤖 Останавливаем бота...")
            bot_process.terminate()
            bot_process.wait(timeout=10)
    except:
        pass
        
    try:
        if 'admin_process' in globals() and admin_process.poll() is None:
            print("🌐 Останавливаем админ-панель...")
            admin_process.terminate()
            admin_process.wait(timeout=10)
    except:
        pass
    
    print("✅ Все сервисы остановлены")
    sys.exit(0)

# Устанавливаем обработчики сигналов
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    print("🚀 Запуск Telegram Channel Finder Bot в production режиме...")
    
    bot_process = None
    admin_process = None
    
    try:
        # Запускаем бота
        print("🤖 Запуск Telegram бота...")
        bot_process = subprocess.Popen([
            sys.executable, "main.py"
        ], env=os.environ.copy())
        
        print(f"✅ Бот запущен (PID: {bot_process.pid})")
        
        # Ждем немного для инициализации бота
        time.sleep(5)
        
        # Запускаем админ-панель
        print("🌐 Запуск админ-панели...")
        admin_process = subprocess.Popen([
            sys.executable, "run_admin.py"
        ], env=os.environ.copy())
        
        print(f"✅ Админ-панель запущена (PID: {admin_process.pid})")
        print("🎉 Все сервисы запущены!")
        print("🤖 Telegram бот: активен")
        print("🌐 Админ-панель: http://0.0.0.0:8080")
        print("📊 Для остановки используйте Ctrl+C")
        
        # Мониторим процессы
        while True:
            # Проверяем статус бота
            if bot_process.poll() is not None:
                print("❌ Бот завершился неожиданно!")
                break
                
            # Проверяем статус админ-панели
            if admin_process.poll() is not None:
                print("❌ Админ-панель завершилась неожиданно!")
                break
                
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Получен сигнал остановки от пользователя")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
    finally:
        signal_handler(signal.SIGTERM, None)
