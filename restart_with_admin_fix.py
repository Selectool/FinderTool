#!/usr/bin/env python3
"""
Перезапуск с исправлением админ методов
"""
import subprocess
import sys
import os
import time
import signal

# Устанавливаем переменные окружения
os.environ["ENVIRONMENT"] = "production"
os.environ["PYTHONPATH"] = "/app"
os.environ["PYTHONUNBUFFERED"] = "1"

class AdminFixManager:
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
        print("🛑 Остановка всех процессов...")
        
        # Останавливаем наши процессы
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
        
        # Убиваем все связанные процессы
        try:
            subprocess.run(["pkill", "-f", "python main.py"], capture_output=True)
            subprocess.run(["pkill", "-f", "python run_admin.py"], capture_output=True)
            subprocess.run(["pkill", "-f", "python bypass_admin.py"], capture_output=True)
        except:
            pass
    
    def start_bot(self):
        """Запуск Telegram бота"""
        try:
            print("🤖 Запуск Telegram бота...")
            self.bot_process = subprocess.Popen(
                [sys.executable, "main.py"],
                env=os.environ.copy(),
                cwd="/app"
            )
            print(f"✅ Бот запущен (PID: {self.bot_process.pid})")
            return True
        except Exception as e:
            print(f"❌ Ошибка запуска бота: {e}")
            return False
    
    def start_admin(self):
        """Запуск админ-панели с исправленными методами"""
        try:
            print("🌐 Запуск админ-панели с исправленными админ методами...")
            
            # Используем стандартный run_admin.py - теперь методы добавлены в ProductionDatabaseManager
            self.admin_process = subprocess.Popen(
                [sys.executable, "run_admin.py"],
                env=os.environ.copy(),
                cwd="/app"
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
        
        print("📊 Запуск мониторинга сервисов...")
        print("🌐 Админ-панель: http://185.207.66.201:8080")
        print("🔧 Админ методы исправлены в ProductionDatabaseManager")
        print("🔑 Логин: admin / admin123")
        print("📊 Мониторинг активен. Для остановки используйте Ctrl+C")
        
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
                
                # Выводим статус
                bot_status = "RUNNING" if (self.bot_process and self.bot_process.poll() is None) else "STOPPED"
                admin_status = "RUNNING" if (self.admin_process and self.admin_process.poll() is None) else "STOPPED"
                
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"{timestamp} - Bot: {bot_status}, Admin: {admin_status}")
                
                # Если оба процесса упали, выходим
                if (self.bot_process and self.bot_process.poll() is not None and 
                    self.admin_process and self.admin_process.poll() is not None):
                    print("❌ Все сервисы завершились!")
                    break
                    
                time.sleep(30)  # Проверяем каждые 30 секунд
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ Ошибка мониторинга: {e}")
                time.sleep(30)
    
    def run(self):
        """Основной метод запуска"""
        print("🚀 Перезапуск с исправлением админ методов...")
        print("🔧 Добавлены методы get_admin_user_by_username и update_admin_user_login")
        
        # Устанавливаем обработчики сигналов
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            # Останавливаем существующие процессы
            self.stop_services()
            time.sleep(5)
            
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
            
            print("🎉 Все сервисы запущены с исправлениями!")
            print("🤖 Telegram бот: активен")
            print("🌐 Админ-панель: http://185.207.66.201:8080")
            print("🔑 Логин: admin / admin123")
            print("✅ Проблема с get_admin_user_by_username исправлена!")
            
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
    manager = AdminFixManager()
    manager.run()
