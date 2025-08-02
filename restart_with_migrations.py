#!/usr/bin/env python3
"""
Перезапуск с выполнением критических миграций для PostgreSQL
Исправляет проблему отсутствующих таблиц admin_users и других
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

class MigrationManager:
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
        """Выполнить критические миграции"""
        print("🔧 Выполнение критических миграций...")
        try:
            # Импортируем и запускаем миграции
            from database.production_migrations import run_production_migrations
            
            database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999!@findertool-hyvrte:5432/findertool_prod')
            await run_production_migrations(database_url)
            
            print("✅ Все критические миграции выполнены")
            return True
        except Exception as e:
            print(f"❌ Ошибка выполнения миграций: {e}")
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
        """Запуск админ-панели с полной схемой БД"""
        try:
            print("🌐 Запуск админ-панели с полной схемой БД...")
            
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
        bot_healthy = True
        admin_healthy = True
        
        print("📊 Запуск мониторинга сервисов...")
        print("🌐 Админ-панель: http://185.207.66.201:8080")
        print("🔑 Логин: admin / admin123")
        print("🔧 Выполнены критические миграции:")
        print("   • Создана таблица admin_users")
        print("   • Создана таблица roles")
        print("   • Создана таблица message_templates")
        print("   • Создана таблица scheduled_broadcasts")
        print("   • Создана таблица audit_logs")
        print("   • Создана таблица ab_tests")
        print("   • Создана таблица broadcast_logs")
        print("   • Создана таблица user_permissions")
        print("   • Расширены таблицы users и broadcast_messages")
        print("   • Вставлены роли и админ пользователь по умолчанию")
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
        print("🚀 Перезапуск с выполнением критических миграций...")
        print("🔧 Исправления:")
        print("   • Создание всех отсутствующих таблиц в PostgreSQL")
        print("   • Полная синхронизация схемы с локальной базой")
        print("   • Создание админ пользователя по умолчанию")
        print("   • Настройка ролей и прав доступа")
        
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            self.stop_services()
            time.sleep(3)
            
            # Выполняем миграции
            print("🔧 Выполнение миграций...")
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
            
            print("🎉 Все сервисы запущены с полной схемой БД!")
            print("🤖 Telegram бот: активен")
            print("🌐 Админ-панель: http://185.207.66.201:8080")
            print("🔑 Логин: admin / admin123")
            print("✅ Схема PostgreSQL полностью синхронизирована!")
            print("✅ Таблица admin_users создана и готова к работе!")
            
            self.monitor_services()
            
        except KeyboardInterrupt:
            print("\n👋 Получен сигнал остановки от пользователя")
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
        finally:
            self.stop_services()
            print("✅ Все сервисы остановлены")

if __name__ == "__main__":
    manager = MigrationManager()
    manager.run()
