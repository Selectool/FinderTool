#!/usr/bin/env python3
"""
Запуск с автоматическими миграциями
Профессиональная система синхронизации схемы БД
"""
import subprocess
import sys
import os
import time
import signal
import asyncio

# Устанавливаем переменные окружения
os.environ["ENVIRONMENT"] = "production"
os.environ["PYTHONPATH"] = "/app"
os.environ["PYTHONUNBUFFERED"] = "1"

class MigrationStartup:
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
    
    def kill_processes_safe(self, process_patterns):
        """Безопасная остановка процессов"""
        try:
            for pattern in process_patterns:
                try:
                    subprocess.run(["pkill", "-f", pattern], capture_output=True)
                except FileNotFoundError:
                    try:
                        result = subprocess.run([
                            "ps", "aux"
                        ], capture_output=True, text=True)
                        
                        for line in result.stdout.split('\n'):
                            if pattern in line and 'ps aux' not in line:
                                parts = line.split()
                                if len(parts) > 1:
                                    pid = parts[1]
                                    try:
                                        subprocess.run(["kill", pid], capture_output=True)
                                        print(f"🔪 Остановлен процесс {pid}: {pattern}")
                                    except:
                                        pass
                    except:
                        pass
        except Exception as e:
            print(f"⚠️ Ошибка остановки процессов: {e}")
    
    def stop_services(self):
        """Остановка всех сервисов"""
        print("🛑 Остановка сервисов...")
        
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
        
        self.kill_processes_safe([
            "python main.py",
            "python run_admin.py",
            "python bypass_admin.py"
        ])
    
    async def run_migrations(self):
        """Выполнить миграции"""
        print("🔧 Применение миграций...")
        try:
            from database.migration_manager import MigrationManager
            
            database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999!@findertool-hyvrte:5432/findertool_prod')
            manager = MigrationManager(database_url)
            
            # Показываем статус до миграций
            print("📊 Статус миграций до применения:")
            await manager.status()
            
            # Применяем миграции
            await manager.migrate()
            
            # Показываем статус после миграций
            print("\n📊 Статус миграций после применения:")
            await manager.status()
            
            print("✅ Все миграции применены успешно")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка выполнения миграций: {e}")
            import traceback
            traceback.print_exc()
            return False
    
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
        """Запуск админ-панели"""
        try:
            print("🌐 Запуск админ-панели...")
            
            admin_env = os.environ.copy()
            admin_env.update({
                "ADMIN_ALLOWED_HOSTS": "185.207.66.201,findertool.dokploy.com,localhost,127.0.0.1,0.0.0.0",
                "ADMIN_CORS_ORIGINS": "http://185.207.66.201:8080,https://findertool.dokploy.com,http://localhost:8080,http://127.0.0.1:8080",
                "ADMIN_HOST": "0.0.0.0",
                "ADMIN_PORT": "8080"
            })
            
            self.admin_process = subprocess.Popen(
                [sys.executable, "run_admin.py"],
                env=admin_env,
                cwd="/app"
            )
            print(f"✅ Админ-панель запущена (PID: {self.admin_process.pid})")
            return True
        except Exception as e:
            print(f"❌ Ошибка запуска админ-панели: {e}")
            return False
    
    def monitor_services(self):
        """Мониторинг сервисов"""
        print("📊 Запуск мониторинга сервисов...")
        print("🌐 Админ-панель: http://185.207.66.201:8080")
        print("🔑 Логин: admin / admin123")
        print("✅ Профессиональная система миграций активна!")
        print("🔄 Схема БД автоматически синхронизирована между локальной и production")
        print("📊 Мониторинг активен. Для остановки используйте Ctrl+C")
        
        while self.running:
            try:
                # Выводим статус
                bot_status = "RUNNING" if (self.bot_process and self.bot_process.poll() is None) else "STOPPED"
                admin_status = "RUNNING" if (self.admin_process and self.admin_process.poll() is None) else "STOPPED"
                
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"{timestamp} - Bot: {bot_status}, Admin: {admin_status}")
                
                if (self.bot_process and self.bot_process.poll() is not None and 
                    self.admin_process and self.admin_process.poll() is not None):
                    print("❌ Все сервисы завершились!")
                    break
                    
                time.sleep(30)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ Ошибка мониторинга: {e}")
                time.sleep(30)
    
    def run(self):
        """Основной метод запуска"""
        print("🚀 Запуск с профессиональной системой миграций...")
        print("🎯 Преимущества:")
        print("   • Автоматическая синхронизация схемы БД")
        print("   • Отслеживание версий миграций")
        print("   • Безопасное применение изменений")
        print("   • Совместимость с SQLite и PostgreSQL")
        print("   • Откат миграций при необходимости")
        
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            self.stop_services()
            time.sleep(3)
            
            # Выполняем миграции
            migration_success = asyncio.run(self.run_migrations())
            
            if not migration_success:
                print("❌ Миграции не выполнены, прерываем запуск")
                return False
            
            if not self.start_bot():
                return False
            
            print("⏳ Ожидание инициализации бота...")
            time.sleep(10)
            
            if not self.start_admin():
                self.stop_services()
                return False
            
            print("⏳ Ожидание инициализации админ-панели...")
            time.sleep(5)
            
            print("🎉 Все сервисы запущены с профессиональной системой миграций!")
            print("🤖 Telegram бот: активен")
            print("🌐 Админ-панель: http://185.207.66.201:8080")
            print("🔑 Логин: admin / admin123")
            print("✅ Схема БД полностью синхронизирована!")
            print("🔄 Система миграций готова к работе!")
            
            self.monitor_services()
            
        except KeyboardInterrupt:
            print("\n👋 Получен сигнал остановки от пользователя")
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
        finally:
            self.stop_services()
            print("✅ Все сервисы остановлены")

if __name__ == "__main__":
    manager = MigrationStartup()
    manager.run()
