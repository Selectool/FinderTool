#!/usr/bin/env python3
"""
Unified launcher для запуска бота и админ-панели в production
"""
import os
import sys
import subprocess
import threading
import time
import signal
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

class UnifiedLauncher:
    """Запускает бот и админ-панель как отдельные процессы"""
    
    def __init__(self):
        self.bot_process = None
        self.admin_process = None
        self.running = True
        
        # Настройка обработчиков сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        print(f"\n🛑 Получен сигнал {signum}, останавливаем сервисы...")
        self.running = False
        self.stop_all()
        sys.exit(0)
    
    def start_bot(self):
        """Запуск Telegram бота"""
        try:
            print("🤖 Запуск Telegram бота...")
            
            # Переменные окружения для бота
            bot_env = os.environ.copy()
            bot_env.update({
                "ENVIRONMENT": "production",
                "SERVICE_TYPE": "telegram-bot"
            })
            
            self.bot_process = subprocess.Popen(
                [sys.executable, "main.py"],
                env=bot_env,
                cwd=os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            print(f"✅ Telegram бот запущен (PID: {self.bot_process.pid})")
            
            # Мониторинг процесса бота
            def monitor_bot():
                while self.running and self.bot_process:
                    try:
                        output = self.bot_process.stdout.readline()
                        if output:
                            print(f"[BOT] {output.strip()}")
                        
                        if self.bot_process.poll() is not None:
                            print("⚠️ Telegram бот завершился")
                            break
                            
                    except Exception as e:
                        print(f"❌ Ошибка мониторинга бота: {e}")
                        break
            
            threading.Thread(target=monitor_bot, daemon=True).start()
            
        except Exception as e:
            print(f"❌ Ошибка запуска бота: {e}")
            return False
        
        return True
    
    def start_admin(self):
        """Запуск админ-панели"""
        try:
            print("🌐 Запуск админ-панели...")
            
            # Переменные окружения для админ-панели
            admin_env = os.environ.copy()
            admin_env.update({
                "ENVIRONMENT": "production",
                "SERVICE_TYPE": "admin-panel",
                "ADMIN_HOST": "0.0.0.0",
                "ADMIN_PORT": "8080",
                "ADMIN_DEBUG": "False"
            })
            
            self.admin_process = subprocess.Popen(
                [sys.executable, "run_admin.py"],
                env=admin_env,
                cwd=os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            print(f"✅ Админ-панель запущена (PID: {self.admin_process.pid})")
            print(f"🌐 Админ-панель доступна: http://0.0.0.0:8080")
            
            # Мониторинг процесса админ-панели
            def monitor_admin():
                while self.running and self.admin_process:
                    try:
                        output = self.admin_process.stdout.readline()
                        if output:
                            print(f"[ADMIN] {output.strip()}")
                        
                        if self.admin_process.poll() is not None:
                            print("⚠️ Админ-панель завершилась")
                            break
                            
                    except Exception as e:
                        print(f"❌ Ошибка мониторинга админ-панели: {e}")
                        break
            
            threading.Thread(target=monitor_admin, daemon=True).start()
            
        except Exception as e:
            print(f"❌ Ошибка запуска админ-панели: {e}")
            return False
        
        return True
    
    def stop_all(self):
        """Остановка всех процессов"""
        print("🛑 Останавливаем все сервисы...")
        
        if self.bot_process:
            try:
                self.bot_process.terminate()
                self.bot_process.wait(timeout=10)
                print("✅ Telegram бот остановлен")
            except subprocess.TimeoutExpired:
                self.bot_process.kill()
                print("🔪 Telegram бот принудительно остановлен")
            except Exception as e:
                print(f"❌ Ошибка остановки бота: {e}")
        
        if self.admin_process:
            try:
                self.admin_process.terminate()
                self.admin_process.wait(timeout=10)
                print("✅ Админ-панель остановлена")
            except subprocess.TimeoutExpired:
                self.admin_process.kill()
                print("🔪 Админ-панель принудительно остановлена")
            except Exception as e:
                print(f"❌ Ошибка остановки админ-панели: {e}")
    
    def run(self):
        """Основной цикл запуска"""
        print("🚀 Запуск Unified Launcher...")
        print("🌍 Environment: production")
        print("📍 Database: PostgreSQL")
        
        # Запускаем сервисы
        bot_started = self.start_bot()
        time.sleep(3)  # Даем боту время на запуск
        
        admin_started = self.start_admin()
        time.sleep(2)  # Даем админ-панели время на запуск
        
        if not bot_started and not admin_started:
            print("❌ Не удалось запустить ни один сервис")
            return False
        
        print("\n🎉 Сервисы запущены:")
        if bot_started:
            print("📱 Telegram бот: ✅ Активен")
        if admin_started:
            print("🌐 Админ-панель: ✅ Активна (http://0.0.0.0:8080)")
        
        # Основной цикл мониторинга
        try:
            while self.running:
                time.sleep(5)
                
                # Проверяем статус процессов
                if self.bot_process and self.bot_process.poll() is not None:
                    print("⚠️ Telegram бот завершился, перезапускаем...")
                    self.start_bot()
                
                if self.admin_process and self.admin_process.poll() is not None:
                    print("⚠️ Админ-панель завершилась, перезапускаем...")
                    self.start_admin()
                    
        except KeyboardInterrupt:
            print("\n👋 Получен сигнал остановки")
        finally:
            self.stop_all()
        
        return True

def main():
    """Точка входа"""
    try:
        # Проверяем окружение
        if not os.getenv("DATABASE_URL"):
            print("❌ DATABASE_URL не установлен")
            return False
        
        launcher = UnifiedLauncher()
        return launcher.run()
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
