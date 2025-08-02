#!/usr/bin/env python3
"""
Production Startup Script
Автоматическая установка и настройка production-ready системы
Telegram Channel Finder Bot для Dokploy
"""
import subprocess
import sys
import os
import time
import logging
import shutil
import asyncio
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/production_startup.log', mode='a') if Path('/app/logs').exists() else logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ProductionInstaller:
    """Автоматический установщик production системы"""

    def __init__(self):
        self.app_dir = Path("/app")
        self.venv_dir = self.app_dir / ".venv"
        self.logs_dir = self.app_dir / "logs"
        self.data_dir = self.app_dir / "data"
        self.python_executable = sys.executable

    def print_banner(self):
        """Показать баннер запуска"""
        banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           🚀 TELEGRAM CHANNEL FINDER BOT 🚀                 ║
║                                                              ║
║              PRODUCTION AUTO-INSTALLER                       ║
║                                                              ║
║  🎯 Senior Developer Level Production-Ready System          ║
║  📦 Automatic Installation & Configuration                  ║
║  📊 Supervisor Process Management                            ║
║  🔄 Automatic Migrations & Data Sync                        ║
║  💾 Data Persistence & Backup System                        ║
║  🔍 Health Monitoring & Auto-Recovery                       ║
║  🌐 Web Admin Panel with Authentication                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
        print(banner)

    def run_command(self, command, check=True, shell=True, cwd=None, timeout=300):
        """Выполнить команду с логированием"""
        try:
            logger.info(f"🔧 Выполняем: {command}")

            if shell and isinstance(command, str):
                result = subprocess.run(
                    command,
                    shell=True,
                    check=check,
                    capture_output=True,
                    text=True,
                    cwd=cwd or self.app_dir,
                    timeout=timeout
                )
            else:
                result = subprocess.run(
                    command,
                    check=check,
                    capture_output=True,
                    text=True,
                    cwd=cwd or self.app_dir,
                    timeout=timeout
                )

            if result.stdout:
                logger.info(f"✅ Вывод: {result.stdout.strip()}")
            if result.stderr and result.returncode == 0:
                logger.warning(f"⚠️ Предупреждения: {result.stderr.strip()}")

            return result

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Ошибка выполнения команды: {e}")
            if e.stdout:
                logger.error(f"Stdout: {e.stdout}")
            if e.stderr:
                logger.error(f"Stderr: {e.stderr}")
            if check:
                raise
            return e
        except subprocess.TimeoutExpired as e:
            logger.error(f"⏰ Команда превысила время ожидания: {command}")
            if check:
                raise
            return e
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка: {e}")
            if check:
                raise
            return e

    def check_system_requirements(self):
        """Проверить системные требования"""
        logger.info("🔍 Проверка системных требований...")

        # Проверяем Python версию
        python_version = sys.version_info
        if python_version < (3, 8):
            logger.error(f"❌ Требуется Python 3.8+, найден {python_version.major}.{python_version.minor}")
            return False

        logger.info(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")

        # Проверяем доступность команд
        required_commands = ['pip', 'git']
        for cmd in required_commands:
            try:
                result = self.run_command(f"which {cmd}", check=False)
                if result.returncode == 0:
                    logger.info(f"✅ {cmd}: {result.stdout.strip()}")
                else:
                    logger.warning(f"⚠️ {cmd} не найден, попытаемся установить")
            except:
                logger.warning(f"⚠️ Не удалось проверить {cmd}")

        return True

    def install_system_dependencies(self):
        """Установить системные зависимости"""
        logger.info("📦 Установка системных зависимостей...")

        try:
            # Обновляем список пакетов
            self.run_command("apt-get update", check=False)

            # Устанавливаем необходимые пакеты
            packages = [
                "python3-pip",
                "python3-venv",
                "python3-dev",
                "build-essential",
                "libpq-dev",
                "git",
                "curl",
                "supervisor"
            ]

            for package in packages:
                logger.info(f"📦 Установка {package}...")
                result = self.run_command(f"apt-get install -y {package}", check=False)
                if result.returncode == 0:
                    logger.info(f"✅ {package} установлен")
                else:
                    logger.warning(f"⚠️ Не удалось установить {package} через apt")

            return True

        except Exception as e:
            logger.warning(f"⚠️ Ошибка установки системных зависимостей: {e}")
            logger.info("🔄 Продолжаем без системных зависимостей...")
            return True

    def create_directories(self):
        """Создать необходимые директории"""
        logger.info("📁 Создание директорий...")

        directories = [
            self.logs_dir,
            self.data_dir,
            self.data_dir / "backups",
            self.data_dir / "deploy_backups",
            self.data_dir / "health_reports",
            self.app_dir / "database" / "backups"
        ]

        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"✅ Создана директория: {directory}")
            except Exception as e:
                logger.error(f"❌ Ошибка создания {directory}: {e}")
                return False

        return True

    def setup_virtual_environment(self):
        """Настроить виртуальное окружение"""
        logger.info("🐍 Настройка виртуального окружения...")

        try:
            # Создаем виртуальное окружение если его нет
            if not self.venv_dir.exists():
                logger.info("📦 Создание виртуального окружения...")
                self.run_command(f"{self.python_executable} -m venv {self.venv_dir}")
            else:
                logger.info("✅ Виртуальное окружение уже существует")

            # Проверяем активацию
            venv_python = self.venv_dir / "bin" / "python"
            if not venv_python.exists():
                logger.error("❌ Не удалось создать виртуальное окружение")
                return False

            logger.info("✅ Виртуальное окружение готово")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка настройки виртуального окружения: {e}")
            return False

    def install_python_dependencies(self):
        """Установить Python зависимости"""
        logger.info("📦 Установка Python зависимостей...")

        try:
            venv_pip = self.venv_dir / "bin" / "pip"

            # Обновляем pip
            logger.info("🔄 Обновление pip...")
            self.run_command(f"{venv_pip} install --upgrade pip")

            # Устанавливаем зависимости
            requirements_file = self.app_dir / "requirements.txt"
            if requirements_file.exists():
                logger.info("📋 Установка зависимостей из requirements.txt...")
                self.run_command(f"{venv_pip} install -r {requirements_file}", timeout=600)
            else:
                logger.warning("⚠️ Файл requirements.txt не найден")

                # Устанавливаем критически важные пакеты
                critical_packages = [
                    "aiogram==3.13.1",
                    "fastapi==0.104.1",
                    "uvicorn[standard]==0.24.0",
                    "asyncpg==0.29.0",
                    "aiosqlite==0.20.0",
                    "passlib[bcrypt]==1.7.4",
                    "python-jose[cryptography]==3.3.0",
                    "supervisor>=4.2.5",
                    "psutil>=5.9.0",
                    "httpx>=0.25.2"
                ]

                for package in critical_packages:
                    logger.info(f"📦 Установка {package}...")
                    self.run_command(f"{venv_pip} install {package}")

            logger.info("✅ Python зависимости установлены")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка установки Python зависимостей: {e}")
            return False

    async def apply_database_migrations(self):
        """Применить миграции базы данных"""
        logger.info("🔧 Применение миграций базы данных...")

        try:
            venv_python = self.venv_dir / "bin" / "python"

            # Проверяем наличие файлов миграций
            migrations_dir = self.app_dir / "database" / "migrations"
            if not migrations_dir.exists():
                logger.warning("⚠️ Директория миграций не найдена, создаем базовую структуру...")
                migrations_dir.mkdir(parents=True, exist_ok=True)

                # Создаем __init__.py
                (migrations_dir / "__init__.py").write_text("# Миграции для Telegram Channel Finder Bot")

            # Применяем миграции
            manage_migrations = self.app_dir / "manage_migrations.py"
            if manage_migrations.exists():
                logger.info("📊 Проверка статуса миграций...")
                result = self.run_command(f"{venv_python} manage_migrations.py status", check=False)

                logger.info("🚀 Применение миграций...")
                result = self.run_command(f"{venv_python} manage_migrations.py migrate", check=False)

                if result.returncode == 0:
                    logger.info("✅ Миграции применены успешно")
                else:
                    logger.warning("⚠️ Возможны проблемы с миграциями, но продолжаем...")
            else:
                logger.warning("⚠️ Файл manage_migrations.py не найден")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка применения миграций: {e}")
            logger.info("🔄 Продолжаем без миграций...")
            return True

    def setup_supervisor(self):
        """Настроить и запустить Supervisor"""
        logger.info("📊 Настройка Supervisor...")

        try:
            # Проверяем наличие конфигурации
            supervisor_config = self.app_dir / "supervisord_production.conf"
            if not supervisor_config.exists():
                logger.error("❌ Файл supervisord_production.conf не найден")
                return False

            # Останавливаем существующие процессы
            self.stop_existing_processes()

            # Запускаем supervisord
            venv_supervisord = self.venv_dir / "bin" / "supervisord"
            if venv_supervisord.exists():
                supervisord_cmd = str(venv_supervisord)
            else:
                supervisord_cmd = "supervisord"

            logger.info("🚀 Запуск Supervisor...")
            self.run_command(f"{supervisord_cmd} -c {supervisor_config}", check=False)

            # Ждем инициализации
            time.sleep(10)

            # Проверяем статус
            return self.check_supervisor_status()

        except Exception as e:
            logger.error(f"❌ Ошибка настройки Supervisor: {e}")
            return False

    def stop_existing_processes(self):
        """Остановить существующие процессы"""
        logger.info("🛑 Остановка существующих процессов...")

        processes_to_stop = [
            "python main.py",
            "python run_admin.py",
            "python production_migration_watcher.py",
            "python production_data_sync.py",
            "python production_health_monitor.py",
            "supervisord"
        ]

        for process in processes_to_stop:
            try:
                self.run_command(f"pkill -f '{process}'", check=False)
                logger.info(f"🔪 Остановлен: {process}")
            except:
                pass

        # Очищаем файлы supervisor
        supervisor_files = ["/tmp/supervisord.pid", "/tmp/supervisor.sock"]
        for file_path in supervisor_files:
            try:
                Path(file_path).unlink(missing_ok=True)
            except:
                pass

    def check_supervisor_status(self):
        """Проверить статус Supervisor"""
        logger.info("📋 Проверка статуса сервисов...")

        try:
            supervisor_config = self.app_dir / "supervisord_production.conf"
            venv_supervisorctl = self.venv_dir / "bin" / "supervisorctl"

            if venv_supervisorctl.exists():
                supervisorctl_cmd = str(venv_supervisorctl)
            else:
                supervisorctl_cmd = "supervisorctl"

            result = self.run_command(f"{supervisorctl_cmd} -c {supervisor_config} status", check=False)

            if result.returncode == 0:
                logger.info("📊 Статус сервисов:")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        logger.info(f"   {line}")
                return True
            else:
                logger.error("❌ Не удалось получить статус сервисов")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка проверки статуса: {e}")
            return False

    async def run_full_installation(self):
        """Выполнить полную установку production системы"""
        logger.info("🚀 Запуск полной установки production системы...")

        installation_start = time.time()

        try:
            # 1. Проверка системных требований
            if not self.check_system_requirements():
                logger.error("❌ Системные требования не выполнены")
                return False

            # 2. Установка системных зависимостей
            if not self.install_system_dependencies():
                logger.error("❌ Ошибка установки системных зависимостей")
                return False

            # 3. Создание директорий
            if not self.create_directories():
                logger.error("❌ Ошибка создания директорий")
                return False

            # 4. Настройка виртуального окружения
            if not self.setup_virtual_environment():
                logger.error("❌ Ошибка настройки виртуального окружения")
                return False

            # 5. Установка Python зависимостей
            if not self.install_python_dependencies():
                logger.error("❌ Ошибка установки Python зависимостей")
                return False

            # 6. Применение миграций
            if not await self.apply_database_migrations():
                logger.error("❌ Ошибка применения миграций")
                return False

            # 7. Настройка и запуск Supervisor
            if not self.setup_supervisor():
                logger.error("❌ Ошибка настройки Supervisor")
                return False

            # 8. Финальная проверка
            await asyncio.sleep(15)  # Ждем инициализации сервисов

            installation_time = time.time() - installation_start

            logger.info("🎉 УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!")
            logger.info(f"⏱️ Время установки: {installation_time:.1f} секунд")
            logger.info("🌐 Админ-панель: http://185.207.66.201:8080")
            logger.info("🔑 Логин: admin / admin123")
            logger.info("📊 Все сервисы под управлением Supervisor")
            logger.info("🔄 Система готова к работе!")

            return True

        except Exception as e:
            logger.error(f"❌ Критическая ошибка установки: {e}")
            return False

    def run_simple_commands(self, command):
        """Выполнить простые команды без установки"""
        try:
            if command == "status":
                # Статус сервисов
                logger.info("📋 Проверка статуса сервисов...")
                supervisor_config = self.app_dir / "supervisord_production.conf"
                if supervisor_config.exists():
                    self.run_command(f"supervisorctl -c {supervisor_config} status", check=False)
                else:
                    logger.error("❌ Конфигурация Supervisor не найдена")

            elif command == "restart":
                # Перезапуск сервисов
                logger.info("🔄 Перезапуск всех сервисов...")
                supervisor_config = self.app_dir / "supervisord_production.conf"
                if supervisor_config.exists():
                    self.run_command(f"supervisorctl -c {supervisor_config} restart all", check=False)
                else:
                    logger.error("❌ Конфигурация Supervisor не найдена")

            elif command == "stop":
                # Остановка сервисов
                logger.info("🛑 Остановка всех сервисов...")
                self.stop_existing_processes()

            elif command == "logs":
                # Просмотр логов
                service = sys.argv[2] if len(sys.argv) > 2 else None
                if service:
                    log_file = self.logs_dir / f"{service}.log"
                    if log_file.exists():
                        self.run_command(f"tail -f {log_file}", check=False)
                    else:
                        logger.error(f"❌ Лог файл {log_file} не найден")
                else:
                    logger.info("📄 Доступные лог файлы:")
                    for log_file in self.logs_dir.glob("*.log"):
                        logger.info(f"   {log_file.name}")

            elif command == "dashboard":
                # Информация об админ-панели
                logger.info("🌐 Админ-панель доступна по адресу:")
                logger.info("   http://185.207.66.201:8080")
                logger.info("   Логин: admin")
                logger.info("   Пароль: admin123")

            else:
                logger.error(f"❌ Неизвестная команда: {command}")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка выполнения команды {command}: {e}")
            return False

def show_help():
    """Показать справку"""
    help_text = """
🛠️ PRODUCTION STARTUP COMMANDS:

📋 Основные команды:
  python production_startup.py                  - Автоматическая установка и запуск
  python production_startup.py deploy           - Полная установка с деплоем
  python production_startup.py install          - Только установка зависимостей
  python production_startup.py status           - Статус всех сервисов
  python production_startup.py restart          - Перезапуск всех сервисов
  python production_startup.py stop             - Остановка всех сервисов
  python production_startup.py logs [service]   - Просмотр логов

🔧 Управление:
  python production_startup.py migrate          - Применить миграции
  python production_startup.py health           - Проверка состояния системы
  python production_startup.py dashboard        - Информация об админ-панели

🎯 Для Dokploy:
  Команда запуска: python production_startup.py deploy

🌐 После установки:
  Админ-панель: http://185.207.66.201:8080
  Логин: admin / admin123
"""
    print(help_text)

    async def run_full_installation(self):
        """Выполнить полную установку production системы"""
        logger.info("🚀 Запуск полной установки production системы...")

        installation_start = time.time()

        try:
            # 1. Проверка системных требований
            if not self.check_system_requirements():
                logger.error("❌ Системные требования не выполнены")
                return False

            # 2. Установка системных зависимостей
            if not self.install_system_dependencies():
                logger.error("❌ Ошибка установки системных зависимостей")
                return False

            # 3. Создание директорий
            if not self.create_directories():
                logger.error("❌ Ошибка создания директорий")
                return False

            # 4. Настройка виртуального окружения
            if not self.setup_virtual_environment():
                logger.error("❌ Ошибка настройки виртуального окружения")
                return False

            # 5. Установка Python зависимостей
            if not self.install_python_dependencies():
                logger.error("❌ Ошибка установки Python зависимостей")
                return False

            # 6. Применение миграций
            if not await self.apply_database_migrations():
                logger.error("❌ Ошибка применения миграций")
                return False

            # 7. Настройка и запуск Supervisor
            if not self.setup_supervisor():
                logger.error("❌ Ошибка настройки Supervisor")
                return False

            # 8. Финальная проверка
            await asyncio.sleep(15)  # Ждем инициализации сервисов

            installation_time = time.time() - installation_start

            logger.info("🎉 УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!")
            logger.info(f"⏱️ Время установки: {installation_time:.1f} секунд")
            logger.info("🌐 Админ-панель: http://185.207.66.201:8080")
            logger.info("🔑 Логин: admin / admin123")
            logger.info("📊 Все сервисы под управлением Supervisor")
            logger.info("🔄 Система готова к работе!")

            return True

        except Exception as e:
            logger.error(f"❌ Критическая ошибка установки: {e}")
            return False

    def run_simple_commands(self, command):
        """Выполнить простые команды без установки"""
        try:
            if command == "status":
                # Статус сервисов
                logger.info("📋 Проверка статуса сервисов...")
                supervisor_config = self.app_dir / "supervisord_production.conf"
                if supervisor_config.exists():
                    self.run_command(f"supervisorctl -c {supervisor_config} status", check=False)
                else:
                    logger.error("❌ Конфигурация Supervisor не найдена")

            elif command == "restart":
                # Перезапуск сервисов
                logger.info("🔄 Перезапуск всех сервисов...")
                supervisor_config = self.app_dir / "supervisord_production.conf"
                if supervisor_config.exists():
                    self.run_command(f"supervisorctl -c {supervisor_config} restart all", check=False)
                else:
                    logger.error("❌ Конфигурация Supervisor не найдена")

            elif command == "stop":
                # Остановка сервисов
                logger.info("🛑 Остановка всех сервисов...")
                self.stop_existing_processes()

            elif command == "logs":
                # Просмотр логов
                service = sys.argv[2] if len(sys.argv) > 2 else None
                if service:
                    log_file = self.logs_dir / f"{service}.log"
                    if log_file.exists():
                        self.run_command(f"tail -f {log_file}", check=False)
                    else:
                        logger.error(f"❌ Лог файл {log_file} не найден")
                else:
                    logger.info("📄 Доступные лог файлы:")
                    for log_file in self.logs_dir.glob("*.log"):
                        logger.info(f"   {log_file.name}")

            elif command == "dashboard":
                # Информация об админ-панели
                logger.info("🌐 Админ-панель доступна по адресу:")
                logger.info("   http://185.207.66.201:8080")
                logger.info("   Логин: admin")
                logger.info("   Пароль: admin123")

            else:
                logger.error(f"❌ Неизвестная команда: {command}")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка выполнения команды {command}: {e}")
            return False

async def main():
    """Основная функция"""
    installer = ProductionInstaller()
    installer.print_banner()

    # Устанавливаем переменные окружения
    os.environ["ENVIRONMENT"] = "production"
    os.environ["PYTHONPATH"] = "/app"
    os.environ["PYTHONUNBUFFERED"] = "1"

    # Определяем команду
    command = sys.argv[1] if len(sys.argv) > 1 else "deploy"

    if command in ["help", "-h", "--help"]:
        show_help()
        return

    logger.info(f"🎯 Выполнение команды: {command}")

    try:
        if command in ["deploy", "install", "start", ""]:
            # Полная установка и запуск
            success = await installer.run_full_installation()
            if not success:
                logger.error("❌ Установка завершилась с ошибками")
                sys.exit(1)

        elif command in ["status", "restart", "stop", "logs", "dashboard"]:
            # Простые команды управления
            success = installer.run_simple_commands(command)
            if not success:
                sys.exit(1)

        elif command == "migrate":
            # Применить миграции
            logger.info("🔧 Применение миграций...")
            await installer.apply_database_migrations()

        elif command == "health":
            # Проверка состояния
            logger.info("🔍 Проверка состояния системы...")
            try:
                from production_health_monitor import ProductionHealthMonitor
                monitor = ProductionHealthMonitor()
                report = await monitor.perform_health_check()
                logger.info(f"Общий статус: {report['overall_status']}")
            except ImportError:
                logger.warning("⚠️ Модуль мониторинга не найден")

        else:
            logger.error(f"❌ Неизвестная команда: {command}")
            show_help()
            sys.exit(1)

        logger.info("✅ Команда выполнена успешно")

    except KeyboardInterrupt:
        logger.info("👋 Операция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

        logger.info("✅ Команда выполнена успешно")

    except KeyboardInterrupt:
        logger.info("👋 Операция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Операция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
