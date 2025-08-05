#!/usr/bin/env python3
"""
Production-Ready Unified Startup Script для Telegram Channel Finder Bot
Запускает и Telegram бота, и админ-панель в одном процессе
Включает автоматические миграции БД, мониторинг и резервное копирование
Оптимизирован для production deployment
"""

import asyncio
import logging
import os
import sys
import signal
import threading
import time
import subprocess
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Создаем необходимые директории ПЕРЕД настройкой логирования
required_dirs = [
    'logs',
    'data',
    'database/backups',
    'uploads/broadcasts',
    'temp'
]

for dir_path in required_dirs:
    Path(dir_path).mkdir(parents=True, exist_ok=True)

# Настройка логирования с обработкой ошибок
def setup_logging():
    """Безопасная настройка логирования"""
    try:
        # Создаем форматтер
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Настраиваем корневой логгер
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # Очищаем существующие обработчики
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # Файловый обработчик с ротацией
        try:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                'logs/unified_startup.log',
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # Если ротация не работает, используем обычный файловый обработчик
            file_handler = logging.FileHandler(
                'logs/unified_startup.log',
                mode='a',
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        return True
    except Exception as e:
        print(f"❌ Ошибка настройки логирования: {e}", file=sys.stderr)
        return False

# Инициализируем логирование
setup_logging()
logger = logging.getLogger(__name__)


class UnifiedService:
    """Production-ready unified сервис для запуска бота и админ-панели"""

    def __init__(self):
        self.bot_task: Optional[asyncio.Task] = None
        self.admin_process: Optional[subprocess.Popen] = None
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.startup_time = datetime.now()
        self.health_stats = {
            'database': {'status': 'unknown', 'last_check': None},
            'admin_panel': {'status': 'unknown', 'last_check': None},
            'telegram_bot': {'status': 'unknown', 'last_check': None}
        }

        # Настройка обработчиков сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("🚀 Инициализация UnifiedService...")

    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"🛑 Получен сигнал {signum}, начинаем graceful shutdown...")
        self.running = False
    
    async def discover_database_host(self) -> Optional[str]:
        """Автоматическое обнаружение правильного хоста базы данных"""
        logger.info("🔍 Автоматическое обнаружение хоста базы данных...")

        # Возможные имена хостов PostgreSQL в Dokploy (в порядке приоритета)
        possible_hosts = [
            'findertool-hyvrte',  # ПРАВИЛЬНОЕ ИМЯ из Dokploy Internal Host
            '185.207.66.201',     # ВНЕШНИЙ IP VPS
            'findertool-db',      # Альтернативное имя
            'postgres',
            'postgresql',
            'db',
            'database',
            'localhost',
            '127.0.0.1',
            'postgres-inGABWIP0OB6grXZXTORS',  # По ID сервиса
            'findertool-postgres',
            'postgres-service'
        ]

        import socket
        from urllib.parse import urlparse
        from config import DATABASE_URL

        # Парсим текущий URL для получения учетных данных
        try:
            parsed = urlparse(DATABASE_URL)
            username = parsed.username or 'findertool_user'
            password = parsed.password or 'Findertool1999!'
            database = parsed.path[1:] if parsed.path else 'findertool_prod'
            port = parsed.port or 5432
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга DATABASE_URL: {e}")
            return None

        # Тестируем каждый возможный хост
        for host in possible_hosts:
            try:
                # Проверяем DNS резолюцию
                socket.gethostbyname(host)

                # Проверяем подключение к порту
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    # Тестируем PostgreSQL подключение
                    test_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
                    try:
                        import psycopg2
                        conn = psycopg2.connect(test_url)
                        conn.close()
                        logger.info(f"✅ Найден рабочий хост: {host}")
                        return test_url
                    except Exception as e:
                        logger.debug(f"❌ PostgreSQL ошибка для {host}: {e}")

            except Exception as e:
                logger.debug(f"❌ Сетевая ошибка для {host}: {e}")

        logger.error("❌ Не найден рабочий хост базы данных")
        return None

    async def wait_for_database(self, max_retries: int = 30) -> bool:
        """Ожидание доступности базы данных с автоматическим обнаружением хоста"""
        logger.info("⏳ Ожидание доступности базы данных...")

        from config import DATABASE_URL
        original_url = DATABASE_URL

        for attempt in range(max_retries):
            try:
                import psycopg2

                # Проверяем подключение с текущим URL
                conn = psycopg2.connect(DATABASE_URL)
                conn.close()
                logger.info("✅ База данных доступна")
                return True

            except Exception as e:
                error_msg = str(e)

                # Если это ошибка DNS резолюции, пытаемся найти правильный хост
                if "could not translate host name" in error_msg or "Name or service not known" in error_msg:
                    if attempt == 0:  # Только при первой попытке
                        logger.warning(f"🔍 DNS ошибка, ищем альтернативный хост: {error_msg}")
                        discovered_url = await self.discover_database_host()

                        if discovered_url:
                            # Обновляем DATABASE_URL в config
                            import config
                            config.DATABASE_URL = discovered_url
                            logger.info(f"🔧 Обновлен DATABASE_URL на: {discovered_url[:50]}...")
                            continue

                if attempt < max_retries - 1:
                    logger.warning(f"⏳ Ожидание БД (попытка {attempt + 1}/{max_retries}): {error_msg}")
                    await asyncio.sleep(2)
                else:
                    logger.error(f"❌ БД недоступна после {max_retries} попыток: {error_msg}")

                    # В последней попытке показываем диагностическую информацию
                    logger.error("🔧 Запустите database_connection_test.py для диагностики")
                    return False

        return False

    async def apply_migrations(self) -> bool:
        """Применение миграций базы данных"""
        try:
            logger.info("🔄 Применение миграций базы данных...")

            # Пытаемся использовать production_manager
            try:
                from database.production_manager import apply_all_migrations
                await apply_all_migrations()
                logger.info("✅ Миграции применены через production_manager")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Ошибка production_manager: {e}")

            # Альтернативный метод через manage_migrations.py
            try:
                logger.info("🔄 Попытка альтернативного применения миграций...")
                result = subprocess.run([
                    sys.executable, "manage_migrations.py", "--apply-all"
                ], capture_output=True, text=True, timeout=120)

                if result.returncode == 0:
                    logger.info("✅ Миграции применены через manage_migrations.py")
                    return True
                else:
                    logger.warning(f"⚠️ Альтернативные миграции: {result.stderr}")

            except Exception as e:
                logger.warning(f"⚠️ Ошибка альтернативного метода: {e}")

            # Если миграции не применились, продолжаем без них
            logger.warning("⚠️ Миграции не применены, продолжаем работу")
            return True

        except Exception as e:
            logger.error(f"❌ Критическая ошибка миграций: {e}")
            return False

    async def init_database(self):
        """Полная инициализация базы данных"""
        try:
            logger.info("🔄 Полная инициализация базы данных...")

            # 1. Ожидаем доступность БД
            if not await self.wait_for_database():
                logger.error("❌ База данных недоступна")
                return False

            # 2. Применяем миграции
            if not await self.apply_migrations():
                logger.error("❌ Не удалось применить миграции")
                return False

            # 3. Инициализируем подключение
            from database.production_manager import init_production_database, db_manager
            from database.db_adapter import set_database

            await init_production_database()
            set_database(db_manager)

            # 4. Проверяем здоровье БД
            health = await db_manager.health_check()
            if health.get('status') == 'healthy':
                logger.info("✅ База данных полностью готова")
                self.health_stats['database'] = {
                    'status': 'healthy',
                    'last_check': datetime.now()
                }
                return True
            else:
                logger.error(f"❌ Проблемы с БД: {health}")
                self.health_stats['database'] = {
                    'status': 'unhealthy',
                    'last_check': datetime.now()
                }
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.health_stats['database'] = {
                'status': 'error',
                'last_check': datetime.now()
            }
            return False
    
    async def start_telegram_bot(self):
        """Запуск Telegram бота с обработкой ошибок"""
        try:
            logger.info("🤖 Запуск Telegram бота...")

            # Проверяем токен
            from config import BOT_TOKEN
            if not BOT_TOKEN:
                raise ValueError("BOT_TOKEN не установлен")

            from aiogram import Bot, Dispatcher
            from aiogram.client.default import DefaultBotProperties
            from aiogram.enums import ParseMode
            from aiogram.fsm.storage.memory import MemoryStorage

            from bot.middlewares.database import DatabaseMiddleware
            from bot.middlewares.role_middleware import RoleMiddleware
            from bot.handlers import basic, channels, subscription, admin, reply_menu

            # Создаем бота с таймаутами
            bot = Bot(
                token=BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )

            # Проверяем валидность токена
            try:
                bot_info = await bot.get_me()
                logger.info(f"✅ Бот подключен: @{bot_info.username}")
            except Exception as e:
                logger.error(f"❌ Неверный токен бота: {e}")
                raise

            # Создаем диспетчер
            dp = Dispatcher(storage=MemoryStorage())

            # Получаем экземпляр базы данных
            from database.universal_database import UniversalDatabase
            from config import DATABASE_URL
            db = UniversalDatabase(DATABASE_URL)

            # Регистрируем middleware
            dp.message.middleware(DatabaseMiddleware(db))
            dp.callback_query.middleware(DatabaseMiddleware(db))
            dp.message.middleware(RoleMiddleware())
            dp.callback_query.middleware(RoleMiddleware())

            # Регистрируем обработчики
            basic.register_handlers(dp)
            channels.register_handlers(dp)
            subscription.register_handlers(dp)
            admin.register_handlers(dp)
            reply_menu.register_handlers(dp)

            logger.info("✅ Telegram бот настроен")
            self.health_stats['telegram_bot'] = {
                'status': 'healthy',
                'last_check': datetime.now()
            }

            # Запускаем polling с обработкой ошибок
            try:
                await dp.start_polling(bot, skip_updates=True)
            except Exception as e:
                logger.error(f"❌ Ошибка polling: {e}")
                self.health_stats['telegram_bot'] = {
                    'status': 'error',
                    'last_check': datetime.now()
                }
                raise

        except Exception as e:
            logger.error(f"❌ Критическая ошибка Telegram бота: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.health_stats['telegram_bot'] = {
                'status': 'error',
                'last_check': datetime.now()
            }
            raise
    
    def start_admin_panel(self):
        """Запуск админ-панели с автоматическим перезапуском"""
        try:
            logger.info("🌐 Запуск админ-панели...")

            restart_count = 0
            max_restarts = 5

            while self.running and restart_count < max_restarts:
                try:
                    # Запускаем админ-панель как subprocess
                    self.admin_process = subprocess.Popen(
                        [sys.executable, "run_admin.py"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=os.getcwd()
                    )

                    logger.info(f"✅ Админ-панель запущена (PID: {self.admin_process.pid})")
                    self.health_stats['admin_panel'] = {
                        'status': 'healthy',
                        'last_check': datetime.now()
                    }

                    # Мониторим процесс
                    while self.running:
                        if self.admin_process.poll() is not None:
                            # Процесс завершился
                            stdout, stderr = self.admin_process.communicate()

                            if stderr:
                                logger.error(f"❌ Админ-панель завершилась с ошибкой: {stderr}")
                            else:
                                logger.warning("⚠️ Админ-панель завершилась")

                            self.health_stats['admin_panel'] = {
                                'status': 'unhealthy',
                                'last_check': datetime.now()
                            }

                            if self.running:
                                restart_count += 1
                                logger.info(f"🔄 Перезапуск админ-панели ({restart_count}/{max_restarts})")
                                time.sleep(5)
                                break
                            else:
                                return

                        time.sleep(10)

                except Exception as e:
                    logger.error(f"❌ Ошибка запуска админ-панели: {e}")
                    restart_count += 1
                    if restart_count < max_restarts:
                        time.sleep(10)

            if restart_count >= max_restarts:
                logger.error(f"❌ Превышено максимальное количество перезапусков админ-панели ({max_restarts})")
                self.health_stats['admin_panel'] = {
                    'status': 'failed',
                    'last_check': datetime.now()
                }

        except Exception as e:
            logger.error(f"❌ Критическая ошибка админ-панели: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.health_stats['admin_panel'] = {
                'status': 'error',
                'last_check': datetime.now()
            }
    
    async def health_check(self):
        """Расширенная проверка здоровья всех сервисов"""
        logger.info("💚 Запуск системы мониторинга здоровья")

        while self.running:
            try:
                current_time = datetime.now()

                # Проверяем БД
                try:
                    from database.production_manager import db_manager
                    db_health = await db_manager.health_check()
                    self.health_stats['database'] = {
                        'status': db_health.get('status', 'unknown'),
                        'last_check': current_time,
                        'details': db_health
                    }
                except Exception as e:
                    logger.error(f"❌ Ошибка проверки БД: {e}")
                    self.health_stats['database'] = {
                        'status': 'error',
                        'last_check': current_time,
                        'error': str(e)
                    }

                # Проверяем админ-панель
                admin_healthy = False
                admin_details = {}

                if self.admin_process and self.admin_process.poll() is None:
                    try:
                        import requests
                        admin_response = requests.get(
                            'http://localhost:8080/api/health',
                            timeout=5
                        )
                        admin_healthy = admin_response.status_code == 200
                        if admin_healthy:
                            admin_details = admin_response.json() if admin_response.content else {}
                    except Exception as e:
                        logger.debug(f"Админ-панель недоступна: {e}")
                        admin_details = {'error': str(e)}

                self.health_stats['admin_panel'] = {
                    'status': 'healthy' if admin_healthy else 'unhealthy',
                    'last_check': current_time,
                    'process_running': self.admin_process and self.admin_process.poll() is None,
                    'details': admin_details
                }

                # Общий статус
                all_healthy = (
                    self.health_stats['database']['status'] == 'healthy' and
                    self.health_stats['admin_panel']['status'] == 'healthy' and
                    self.health_stats['telegram_bot']['status'] == 'healthy'
                )

                if all_healthy:
                    logger.debug("💚 Все сервисы здоровы")
                else:
                    status_summary = {
                        'БД': self.health_stats['database']['status'],
                        'Админ': self.health_stats['admin_panel']['status'],
                        'Бот': self.health_stats['telegram_bot']['status']
                    }
                    logger.warning(f"⚠️ Статус сервисов: {status_summary}")

                # Логируем подробную статистику каждые 10 минут
                if current_time.minute % 10 == 0:
                    uptime = current_time - self.startup_time
                    logger.info(f"📊 Uptime: {uptime}, Статус: {status_summary}")

                await asyncio.sleep(60)  # Проверяем каждую минуту

            except Exception as e:
                logger.error(f"❌ Ошибка health check: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                await asyncio.sleep(60)
    
    async def backup_data(self):
        """Автоматическое резервное копирование данных"""
        logger.info("💾 Запуск системы автоматического резервного копирования")

        while self.running:
            try:
                # Ждем час перед первым бэкапом
                await asyncio.sleep(3600)

                if not self.running:
                    break

                logger.info("💾 Создание резервной копии данных...")

                # Создаем бэкап БД
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"database/backups/backup_{timestamp}.sql"

                try:
                    # Используем pg_dump для создания бэкапа
                    database_url = os.getenv('DATABASE_URL')
                    if database_url:
                        result = subprocess.run([
                            "pg_dump", database_url, "-f", backup_file
                        ], capture_output=True, text=True, timeout=300)

                        if result.returncode == 0:
                            logger.info(f"✅ Резервная копия создана: {backup_file}")

                            # Удаляем старые бэкапы (оставляем последние 10)
                            backup_dir = Path("database/backups")
                            backups = sorted(backup_dir.glob("backup_*.sql"))
                            if len(backups) > 10:
                                for old_backup in backups[:-10]:
                                    old_backup.unlink()
                                    logger.info(f"🗑️ Удален старый бэкап: {old_backup.name}")
                        else:
                            logger.error(f"❌ Ошибка создания бэкапа: {result.stderr}")
                    else:
                        logger.warning("⚠️ DATABASE_URL не установлен, пропускаем бэкап")

                except Exception as e:
                    logger.error(f"❌ Ошибка резервного копирования: {e}")

            except Exception as e:
                logger.error(f"❌ Критическая ошибка backup_data: {e}")
                await asyncio.sleep(3600)

    async def run(self):
        """Главный метод запуска production-ready unified сервиса"""
        logger.info("🚀 Запуск Production-Ready Unified Telegram Channel Finder Bot Service")
        logger.info(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'production')}")
        logger.info(f"📍 Database: {os.getenv('DATABASE_URL', 'не установлен')[:50]}...")
        logger.info(f"🕐 Время запуска: {self.startup_time}")

        self.running = True

        try:
            # 1. Инициализация базы данных с миграциями
            logger.info("📊 Этап 1: Инициализация базы данных...")
            if not await self.init_database():
                logger.error("💥 Критическая ошибка: не удалось инициализировать базу данных")
                sys.exit(1)

            # 2. Запуск админ-панели в отдельном потоке
            logger.info("🌐 Этап 2: Запуск админ-панели...")
            admin_thread = threading.Thread(target=self.start_admin_panel, daemon=True)
            admin_thread.start()

            # Ждем запуска админ-панели
            await asyncio.sleep(10)

            # 3. Создаем и запускаем основные задачи
            logger.info("🤖 Этап 3: Запуск основных сервисов...")
            tasks = []

            # Telegram бот
            self.bot_task = asyncio.create_task(self.start_telegram_bot())
            tasks.append(self.bot_task)

            # Health check
            health_task = asyncio.create_task(self.health_check())
            tasks.append(health_task)

            # Backup task
            backup_task = asyncio.create_task(self.backup_data())
            tasks.append(backup_task)

            logger.info("🎉 Все сервисы успешно запущены!")
            logger.info("📱 Telegram бот: Активен")
            logger.info("🌐 Админ-панель: http://localhost:8080")
            logger.info("💾 Автоматические бэкапы: Включены")
            logger.info("💚 Мониторинг здоровья: Активен")

            # Ждем завершения задач
            await asyncio.gather(*tasks, return_exceptions=True)

        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки от пользователя")
        except Exception as e:
            logger.error(f"💥 Критическая ошибка в main loop: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            await self._graceful_shutdown(tasks if 'tasks' in locals() else [])

    async def _graceful_shutdown(self, tasks):
        """Graceful shutdown всех сервисов"""
        logger.info("🔄 Начинаем graceful shutdown...")
        self.running = False

        # Останавливаем админ-панель
        if self.admin_process and self.admin_process.poll() is None:
            logger.info("🌐 Остановка админ-панели...")
            self.admin_process.terminate()
            try:
                self.admin_process.wait(timeout=15)
                logger.info("✅ Админ-панель остановлена")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Принудительная остановка админ-панели...")
                self.admin_process.kill()
                self.admin_process.wait()

        # Отменяем все задачи
        if tasks:
            logger.info("🤖 Остановка асинхронных задач...")
            for task in tasks:
                if not task.done():
                    task.cancel()

            # Ждем завершения с таймаутом
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=30
                )
                logger.info("✅ Все задачи остановлены")
            except asyncio.TimeoutError:
                logger.warning("⚠️ Таймаут остановки задач")

        # Закрываем executor
        if self.executor:
            self.executor.shutdown(wait=True)
            logger.info("✅ ThreadPoolExecutor остановлен")

        uptime = datetime.now() - self.startup_time
        logger.info(f"✅ Unified сервис остановлен. Время работы: {uptime}")


async def main():
    """Главная функция с обработкой ошибок"""
    try:
        logger.info("🚀 Инициализация главного процесса...")
        service = UnifiedService()
        await service.run()
    except Exception as e:
        logger.error(f"💥 Критическая ошибка в main(): {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


def run_with_error_handling():
    """Запуск с полной обработкой ошибок"""
    try:
        # Проверяем Python версию
        if sys.version_info < (3, 8):
            logger.error("❌ Требуется Python 3.8 или выше")
            sys.exit(1)

        # Проверяем критические переменные окружения
        required_env_vars = ['BOT_TOKEN', 'DATABASE_URL']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            logger.error(f"❌ Отсутствуют переменные окружения: {missing_vars}")
            sys.exit(1)

        logger.info("✅ Предварительные проверки пройдены")

        # Запускаем основной процесс
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("🛑 Прерывание пользователем")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"💥 Необработанная критическая ошибка: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    run_with_error_handling()
