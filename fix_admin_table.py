#!/usr/bin/env python3
"""
Быстрое исправление: создание таблицы admin_users и проверка входа
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

class AdminTableFixer:
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
    
    async def fix_admin_table(self):
        """Исправить таблицу admin_users"""
        print("🔧 Исправление таблицы admin_users...")
        try:
            from database.db_adapter import DatabaseAdapter
            from passlib.context import CryptContext
            
            database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999!@findertool-hyvrte:5432/findertool_prod')
            adapter = DatabaseAdapter(database_url)
            await adapter.connect()
            
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            try:
                # Проверяем, существует ли таблица admin_users
                check_table_query = """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'admin_users'
                    );
                """
                result = await adapter.fetch_one(check_table_query)
                table_exists = result[0] if result else False
                
                if not table_exists:
                    print("📋 Создание таблицы admin_users...")
                    create_table_query = """
                        CREATE TABLE admin_users (
                            id SERIAL PRIMARY KEY,
                            username VARCHAR(255) UNIQUE NOT NULL,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            role VARCHAR(100) NOT NULL DEFAULT 'moderator',
                            is_active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_login TIMESTAMP,
                            created_by INTEGER,
                            FOREIGN KEY (created_by) REFERENCES admin_users (id)
                        )
                    """
                    await adapter.execute(create_table_query)
                    print("✅ Таблица admin_users создана")
                else:
                    print("✅ Таблица admin_users уже существует")
                
                # Проверяем, есть ли админ пользователи
                count_query = "SELECT COUNT(*) FROM admin_users"
                result = await adapter.fetch_one(count_query)
                count = result[0] if result else 0
                
                if count == 0:
                    print("👤 Создание админ пользователя по умолчанию...")
                    default_password = "admin123"
                    password_hash = pwd_context.hash(default_password)
                    
                    insert_query = """
                        INSERT INTO admin_users (username, email, password_hash, role, is_active)
                        VALUES ($1, $2, $3, $4, $5)
                    """
                    
                    await adapter.execute(insert_query, ("admin", "admin@localhost", password_hash, "super_admin", True))
                    print(f"✅ Создан админ пользователь: admin / {default_password}")
                    print("⚠️ ОБЯЗАТЕЛЬНО измените пароль после первого входа!")
                else:
                    print(f"✅ Найдено {count} админ пользователей")
                
                # Проверяем, можем ли мы получить админ пользователя
                test_query = "SELECT username, role FROM admin_users WHERE username = $1"
                result = await adapter.fetch_one(test_query, ("admin",))
                
                if result:
                    print(f"✅ Тест успешен: найден пользователь {result[0]} с ролью {result[1]}")
                else:
                    print("⚠️ Пользователь admin не найден")
                
                await adapter.disconnect()
                print("✅ Исправление таблицы admin_users завершено")
                return True
                
            except Exception as e:
                print(f"❌ Ошибка работы с БД: {e}")
                await adapter.disconnect()
                return False
                
        except Exception as e:
            print(f"❌ Ошибка исправления таблицы: {e}")
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
        print("✅ Таблица admin_users исправлена и готова к работе!")
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
        print("🚀 Быстрое исправление таблицы admin_users...")
        print("🔧 Исправления:")
        print("   • Проверка и создание таблицы admin_users")
        print("   • Создание админ пользователя по умолчанию")
        print("   • Тестирование доступа к таблице")
        
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            self.stop_services()
            time.sleep(3)
            
            # Исправляем таблицу admin_users
            print("🔧 Исправление таблицы admin_users...")
            fix_success = asyncio.run(self.fix_admin_table())
            
            if not fix_success:
                print("❌ Исправление не выполнено, прерываем запуск")
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
            
            print("🎉 Все сервисы запущены!")
            print("🤖 Telegram бот: активен")
            print("🌐 Админ-панель: http://185.207.66.201:8080")
            print("🔑 Логин: admin / admin123")
            print("✅ Таблица admin_users исправлена и готова!")
            
            self.monitor_services()
            
        except KeyboardInterrupt:
            print("\n👋 Получен сигнал остановки от пользователя")
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
        finally:
            self.stop_services()
            print("✅ Все сервисы остановлены")

if __name__ == "__main__":
    manager = AdminTableFixer()
    manager.run()
