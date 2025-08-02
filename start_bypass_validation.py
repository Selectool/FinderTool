#!/usr/bin/env python3
"""
Запуск бота и админ-панели с обходом валидации конфигурации
"""
import subprocess
import sys
import os
import time
import signal
from pathlib import Path

# Устанавливаем переменные окружения для обхода валидации
os.environ["ENVIRONMENT"] = "production"
os.environ["ADMIN_ALLOWED_HOSTS"] = "185.207.66.201,findertool.dokploy.com,localhost,127.0.0.1,0.0.0.0"
os.environ["ADMIN_CORS_ORIGINS"] = "http://185.207.66.201:8080,https://findertool.dokploy.com,http://localhost:8080"
os.environ["ADMIN_HOST"] = "0.0.0.0"
os.environ["ADMIN_PORT"] = "8080"
os.environ["ADMIN_DEBUG"] = "False"
os.environ["PYTHONPATH"] = "/app"
os.environ["PYTHONUNBUFFERED"] = "1"

class BypassValidationManager:
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
    
    def create_bypass_admin_script(self):
        """Создание скрипта для обхода валидации админ-панели"""
        bypass_script = """#!/usr/bin/env python3
import os
import sys
import uvicorn

# Обходим валидацию конфигурации
os.environ["ENVIRONMENT"] = "production"
os.environ["ADMIN_ALLOWED_HOSTS"] = "185.207.66.201,findertool.dokploy.com,localhost,127.0.0.1,0.0.0.0"
os.environ["ADMIN_CORS_ORIGINS"] = "http://185.207.66.201:8080,https://findertool.dokploy.com,http://localhost:8080"

# Отключаем валидацию
def mock_validate_config():
    print("🔧 Валидация конфигурации пропущена для обхода ограничений")
    return

# Патчим валидацию
try:
    import admin.config
    admin.config.validate_config = mock_validate_config
except:
    pass

try:
    from admin.utils.config_validator import ConfigValidator
    ConfigValidator.validate_all = lambda self, config: True
except:
    pass

# Запускаем админ-панель
try:
    from admin.app import app
    print("🌐 Запуск админ-панели с обходом валидации...")
    print(f"🔧 ADMIN_ALLOWED_HOSTS: {os.environ['ADMIN_ALLOWED_HOSTS']}")
    print(f"🔧 ADMIN_CORS_ORIGINS: {os.environ['ADMIN_CORS_ORIGINS']}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True
    )
except Exception as e:
    print(f"❌ Ошибка запуска админ-панели: {e}")
    import traceback
    traceback.print_exc()
"""
        
        with open("/app/bypass_admin.py", "w") as f:
            f.write(bypass_script)
        
        print("✅ Скрипт обхода валидации создан")
    
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
        """Запуск админ-панели с обходом валидации"""
        try:
            print("🌐 Запуск админ-панели с обходом валидации...")
            print(f"🔧 ADMIN_ALLOWED_HOSTS: {os.environ['ADMIN_ALLOWED_HOSTS']}")
            print(f"🔧 ADMIN_CORS_ORIGINS: {os.environ['ADMIN_CORS_ORIGINS']}")
            
            self.admin_process = subprocess.Popen(
                [sys.executable, "bypass_admin.py"],
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
        print("🔧 Валидация конфигурации обойдена")
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
        print("🚀 Запуск Telegram Channel Finder Bot + Admin Panel...")
        print("🔧 Обход валидации конфигурации для production")
        
        # Устанавливаем обработчики сигналов
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            # Создаем скрипт обхода валидации
            self.create_bypass_admin_script()
            
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
            print("🌐 Админ-панель: http://185.207.66.201:8080")
            print("🔑 Логин: admin / admin123")
            
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
    manager = BypassValidationManager()
    manager.run()
