#!/usr/bin/env python3
"""
Запуск Telegram бота и админ-панели в одном процессе
"""
import asyncio
import threading
import subprocess
import signal
import sys
import os
import time
from pathlib import Path

# Устанавливаем продакшн режим
os.environ["ENVIRONMENT"] = "production"

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

class ServiceManager:
    def __init__(self):
        self.bot_process = None
        self.admin_process = None
        self.running = True
        
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        print(f"\n🛑 Получен сигнал {signum}, останавливаем сервисы...")
        self.running = False
        self.stop_services()
        sys.exit(0)
    
    def stop_services(self):
        """Остановка всех сервисов"""
        if self.bot_process and self.bot_process.poll() is None:
            print("🤖 Останавливаем бота...")
            self.bot_process.terminate()
            try:
                self.bot_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.bot_process.kill()
                
        if self.admin_process and self.admin_process.poll() is None:
            print("🌐 Останавливаем админ-панель...")
            self.admin_process.terminate()
            try:
                self.admin_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.admin_process.kill()
    
    def start_bot(self):
        """Запуск Telegram бота"""
        try:
            print("🤖 Запуск Telegram бота...")
            self.bot_process = subprocess.Popen(
                [sys.executable, "main.py"],
                env=os.environ.copy(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            print(f"✅ Бот запущен (PID: {self.bot_process.pid})")
            return True
        except Exception as e:
            print(f"❌ Ошибка запуска бота: {e}")
            return False
    
    def start_admin(self):
        """Запуск админ-панели"""
        try:
            print("🌐 Запуск админ-панели...")
            self.admin_process = subprocess.Popen(
                [sys.executable, "run_admin.py"],
                env=os.environ.copy(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            print(f"✅ Админ-панель запущена (PID: {self.admin_process.pid})")
            return True
        except Exception as e:
            print(f"❌ Ошибка запуска админ-панели: {e}")
            return False
    
    def monitor_services(self):
        """Мониторинг сервисов"""
        bot_healthy = True
        admin_healthy = True
        
        while self.running:
            try:
                # Проверяем статус бота
                if self.bot_process:
                    if self.bot_process.poll() is not None:
                        if bot_healthy:
                            print("❌ Бот завершился неожиданно!")
                            bot_healthy = False
                    else:
                        if not bot_healthy:
                            print("✅ Бот восстановлен")
                            bot_healthy = True
                
                # Проверяем статус админ-панели
                if self.admin_process:
                    if self.admin_process.poll() is not None:
                        if admin_healthy:
                            print("❌ Админ-панель завершилась неожиданно!")
                            admin_healthy = False
                    else:
                        if not admin_healthy:
                            print("✅ Админ-панель восстановлена")
                            admin_healthy = True
                
                # Если оба процесса упали, выходим
                if (self.bot_process and self.bot_process.poll() is not None and 
                    self.admin_process and self.admin_process.poll() is not None):
                    print("❌ Все сервисы завершились!")
                    break
                    
                time.sleep(5)  # Проверяем каждые 5 секунд
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ Ошибка мониторинга: {e}")
                time.sleep(5)
    
    def run(self):
        """Основной метод запуска"""
        print("🚀 Запуск Telegram Channel Finder Bot + Admin Panel...")
        
        # Устанавливаем обработчики сигналов
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            # Запускаем бота
            if not self.start_bot():
                return False
            
            # Ждем инициализации бота
            print("⏳ Ожидание инициализации бота...")
            time.sleep(10)
            
            # Запускаем админ-панель
            if not self.start_admin():
                self.stop_services()
                return False
            
            # Ждем инициализации админ-панели
            print("⏳ Ожидание инициализации админ-панели...")
            time.sleep(5)
            
            print("🎉 Все сервисы запущены!")
            print("🤖 Telegram бот: активен")
            print("🌐 Админ-панель: http://0.0.0.0:8080")
            print("📊 Мониторинг активен. Для остановки используйте Ctrl+C")
            
            # Запускаем мониторинг
            self.monitor_services()
            
        except KeyboardInterrupt:
            print("\n👋 Получен сигнал остановки от пользователя")
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
        finally:
            self.stop_services()
            print("✅ Все сервисы остановлены")

if __name__ == "__main__":
    manager = ServiceManager()
    manager.run()
