#!/usr/bin/env python3
"""
Production Supervisor Manager
Управление всеми сервисами через Supervisor
"""
import subprocess
import sys
import os
import time
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class ProductionSupervisorManager:
    """Менеджер Supervisor для production"""
    
    def __init__(self):
        self.config_file = "/app/supervisord_production.conf"
        self.pid_file = "/tmp/supervisord.pid"
        self.sock_file = "/tmp/supervisor.sock"
        
    def install_supervisor(self):
        """Установить Supervisor если не установлен"""
        try:
            subprocess.run(["supervisord", "--version"], capture_output=True, check=True)
            logger.info("✅ Supervisor уже установлен")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.info("📦 Установка Supervisor...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "supervisor"], check=True)
                logger.info("✅ Supervisor установлен")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Ошибка установки Supervisor: {e}")
                return False
    
    def create_directories(self):
        """Создать необходимые директории"""
        directories = [
            "/app/logs",
            "/app/data",
            "/app/data/backups",
            "/app/data/health_reports"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Создана директория: {directory}")
    
    def stop_existing_processes(self):
        """Остановить существующие процессы"""
        logger.info("🛑 Остановка существующих процессов...")
        
        processes_to_stop = [
            "python main.py",
            "python run_admin.py",
            "python start_with_migrations.py",
            "python production_migration_watcher.py",
            "python production_data_sync.py",
            "python production_health_monitor.py"
        ]
        
        for process_pattern in processes_to_stop:
            try:
                subprocess.run(["pkill", "-f", process_pattern], capture_output=True)
                logger.info(f"🔪 Остановлен: {process_pattern}")
            except:
                pass
        
        # Остановить существующий supervisord
        try:
            if Path(self.pid_file).exists():
                subprocess.run(["supervisorctl", "-c", self.config_file, "shutdown"], capture_output=True)
                time.sleep(2)
        except:
            pass
        
        # Принудительно убить supervisord если нужно
        try:
            subprocess.run(["pkill", "-f", "supervisord"], capture_output=True)
        except:
            pass
        
        # Очистить файлы
        for file_path in [self.pid_file, self.sock_file]:
            try:
                Path(file_path).unlink(missing_ok=True)
            except:
                pass
    
    def start_supervisor(self):
        """Запустить Supervisor"""
        logger.info("🚀 Запуск Supervisor...")
        
        try:
            # Запускаем supervisord
            result = subprocess.run([
                "supervisord", 
                "-c", self.config_file,
                "-n"  # Не демонизируем для лучшего контроля
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info("✅ Supervisor запущен успешно")
                return True
            else:
                logger.error(f"❌ Ошибка запуска Supervisor: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.info("⏱️ Supervisor запущен в фоновом режиме")
            return True
        except Exception as e:
            logger.error(f"❌ Критическая ошибка запуска Supervisor: {e}")
            return False
    
    def check_services_status(self):
        """Проверить статус сервисов"""
        logger.info("📊 Проверка статуса сервисов...")
        
        try:
            result = subprocess.run([
                "supervisorctl", "-c", self.config_file, "status"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info("📋 Статус сервисов:")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        logger.info(f"   {line}")
                return True
            else:
                logger.error(f"❌ Ошибка получения статуса: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки статуса: {e}")
            return False
    
    def restart_all_services(self):
        """Перезапустить все сервисы"""
        logger.info("🔄 Перезапуск всех сервисов...")
        
        try:
            result = subprocess.run([
                "supervisorctl", "-c", self.config_file, "restart", "all"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info("✅ Все сервисы перезапущены")
                return True
            else:
                logger.error(f"❌ Ошибка перезапуска: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка перезапуска сервисов: {e}")
            return False
    
    def show_logs(self, service_name=None, lines=50):
        """Показать логи сервиса"""
        if service_name:
            logger.info(f"📄 Логи сервиса {service_name} (последние {lines} строк):")
            cmd = ["supervisorctl", "-c", self.config_file, "tail", "-f", service_name]
        else:
            logger.info(f"📄 Логи всех сервисов:")
            cmd = ["supervisorctl", "-c", self.config_file, "tail", "-f"]
        
        try:
            subprocess.run(cmd, timeout=10)
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            logger.error(f"❌ Ошибка получения логов: {e}")
    
    def run_production_setup(self):
        """Полная настройка production окружения"""
        logger.info("🎯 Настройка Production окружения с Supervisor...")
        
        # 1. Установка Supervisor
        if not self.install_supervisor():
            return False
        
        # 2. Создание директорий
        self.create_directories()
        
        # 3. Остановка существующих процессов
        self.stop_existing_processes()
        
        # 4. Ожидание завершения процессов
        time.sleep(5)
        
        # 5. Запуск Supervisor
        if not self.start_supervisor():
            return False
        
        # 6. Ожидание инициализации
        time.sleep(10)
        
        # 7. Проверка статуса
        self.check_services_status()
        
        logger.info("🎉 Production окружение настроено!")
        logger.info("🌐 Админ-панель: http://185.207.66.201:8080")
        logger.info("🔑 Логин: admin / admin123")
        logger.info("📊 Мониторинг: все сервисы под управлением Supervisor")
        
        return True

def main():
    """Основная функция"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        manager = ProductionSupervisorManager()
        
        if command == "start":
            manager.run_production_setup()
        elif command == "status":
            manager.check_services_status()
        elif command == "restart":
            manager.restart_all_services()
        elif command == "logs":
            service = sys.argv[2] if len(sys.argv) > 2 else None
            manager.show_logs(service)
        elif command == "stop":
            manager.stop_existing_processes()
        else:
            print("Доступные команды: start, status, restart, logs [service], stop")
    else:
        # По умолчанию запускаем полную настройку
        manager = ProductionSupervisorManager()
        manager.run_production_setup()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Операция прервана пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
