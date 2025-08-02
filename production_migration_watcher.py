#!/usr/bin/env python3
"""
Production Migration Watcher
Отслеживает изменения в схеме БД и автоматически применяет миграции
"""
import asyncio
import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
import hashlib
import json

# Устанавливаем переменные окружения
os.environ["ENVIRONMENT"] = "production"
os.environ["PYTHONPATH"] = "/app"
os.environ["PYTHONUNBUFFERED"] = "1"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/migration-watcher.log')
    ]
)
logger = logging.getLogger(__name__)

class ProductionMigrationWatcher:
    """Наблюдатель за миграциями в production"""
    
    def __init__(self):
        self.migrations_dir = Path("/app/database/migrations")
        self.state_file = Path("/app/data/migration_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.check_interval = 30  # секунд
        self.last_migration_hash = None
        
    def get_migrations_hash(self) -> str:
        """Получить хеш всех файлов миграций"""
        if not self.migrations_dir.exists():
            return ""
        
        migration_files = sorted(self.migrations_dir.glob("*.py"))
        content = ""
        
        for file_path in migration_files:
            if file_path.name != "__init__.py":
                try:
                    content += file_path.read_text(encoding='utf-8')
                except Exception as e:
                    logger.warning(f"Не удалось прочитать {file_path}: {e}")
        
        return hashlib.md5(content.encode()).hexdigest()
    
    def load_state(self) -> dict:
        """Загрузить состояние из файла"""
        try:
            if self.state_file.exists():
                return json.loads(self.state_file.read_text())
        except Exception as e:
            logger.warning(f"Ошибка загрузки состояния: {e}")
        
        return {
            "last_migration_hash": "",
            "last_check": None,
            "migration_count": 0
        }
    
    def save_state(self, state: dict):
        """Сохранить состояние в файл"""
        try:
            state["last_check"] = datetime.now().isoformat()
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}")
    
    async def check_and_apply_migrations(self):
        """Проверить и применить новые миграции"""
        try:
            current_hash = self.get_migrations_hash()
            state = self.load_state()
            
            if current_hash != state.get("last_migration_hash"):
                logger.info("🔍 Обнаружены изменения в миграциях")
                
                # Применяем миграции
                from database.migration_manager import MigrationManager
                
                database_url = os.getenv('DATABASE_URL', 'postgresql://findertool_user:Findertool1999!@findertool-hyvrte:5432/findertool_prod')
                manager = MigrationManager(database_url)
                
                logger.info("🚀 Применение новых миграций...")
                await manager.migrate()
                
                # Обновляем состояние
                state["last_migration_hash"] = current_hash
                state["migration_count"] = len(manager.discover_migrations())
                self.save_state(state)
                
                logger.info("✅ Миграции успешно применены")
                
                # Уведомляем другие сервисы о необходимости перезагрузки
                await self.notify_services_restart()
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки миграций: {e}")
    
    async def notify_services_restart(self):
        """Уведомить сервисы о необходимости перезагрузки"""
        try:
            # Создаем файл-флаг для перезагрузки
            restart_flag = Path("/app/data/restart_required.flag")
            restart_flag.write_text(datetime.now().isoformat())
            
            logger.info("🔄 Создан флаг для перезагрузки сервисов")
            
        except Exception as e:
            logger.error(f"Ошибка создания флага перезагрузки: {e}")
    
    async def run(self):
        """Основной цикл наблюдателя"""
        logger.info("🔍 Запуск Production Migration Watcher...")
        logger.info(f"📁 Отслеживаем: {self.migrations_dir}")
        logger.info(f"⏱️ Интервал проверки: {self.check_interval} секунд")
        
        # Первоначальная проверка
        await self.check_and_apply_migrations()
        
        while True:
            try:
                await asyncio.sleep(self.check_interval)
                await self.check_and_apply_migrations()
                
            except KeyboardInterrupt:
                logger.info("👋 Получен сигнал остановки")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле наблюдателя: {e}")
                await asyncio.sleep(self.check_interval)

if __name__ == "__main__":
    try:
        watcher = ProductionMigrationWatcher()
        asyncio.run(watcher.run())
    except KeyboardInterrupt:
        logger.info("👋 Migration Watcher остановлен")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
