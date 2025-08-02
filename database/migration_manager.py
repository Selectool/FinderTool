"""
Профессиональная система миграций для Telegram Channel Finder Bot
Поддерживает SQLite (локально) и PostgreSQL (production)
"""
import os
import logging
import importlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from database.db_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)

class Migration:
    """Базовый класс для миграций"""
    
    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description
        self.applied_at = None
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        raise NotImplementedError("Метод up() должен быть реализован")
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        raise NotImplementedError("Метод down() должен быть реализован")
    
    def __str__(self):
        return f"Migration {self.version}: {self.description}"

class MigrationManager:
    """Менеджер миграций"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.migrations_dir = Path(__file__).parent / "migrations"
        self.migrations_dir.mkdir(exist_ok=True)
        
    async def init_migrations_table(self):
        """Создать таблицу для отслеживания миграций"""
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            if adapter.db_type == 'sqlite':
                query = """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(255) PRIMARY KEY,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            else:  # PostgreSQL
                query = """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(255) PRIMARY KEY,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            
            await adapter.execute(query)
            logger.info("✅ Таблица schema_migrations готова")
            
        finally:
            await adapter.disconnect()
    
    async def get_applied_migrations(self) -> List[str]:
        """Получить список примененных миграций"""
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            await self.init_migrations_table()
            
            if adapter.db_type == 'sqlite':
                query = "SELECT version FROM schema_migrations ORDER BY version"
            else:  # PostgreSQL
                query = "SELECT version FROM schema_migrations ORDER BY version"
            
            result = await adapter.fetch_all(query)
            
            # Обрабатываем результат в зависимости от формата
            versions = []
            if result:
                for row in result:
                    if isinstance(row, (list, tuple)):
                        versions.append(row[0])
                    elif isinstance(row, dict):
                        versions.append(row['version'])
                    else:
                        versions.append(str(row))
            
            return versions
            
        finally:
            await adapter.disconnect()
    
    def discover_migrations(self) -> List[str]:
        """Найти все файлы миграций"""
        migration_files = []
        
        if self.migrations_dir.exists():
            for file_path in sorted(self.migrations_dir.glob("*.py")):
                if file_path.name != "__init__.py":
                    # Извлекаем версию из имени файла (например, 001_initial.py -> 001)
                    version = file_path.stem.split('_')[0]
                    migration_files.append(version)
        
        return migration_files
    
    async def load_migration(self, version: str) -> Migration:
        """Загрузить миграцию по версии"""
        # Находим файл миграции
        migration_file = None
        for file_path in self.migrations_dir.glob(f"{version}_*.py"):
            migration_file = file_path
            break
        
        if not migration_file:
            raise FileNotFoundError(f"Миграция {version} не найдена")
        
        # Импортируем модуль миграции
        module_name = f"database.migrations.{migration_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, migration_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Получаем класс миграции
        migration_class = getattr(module, 'Migration')
        return migration_class()
    
    async def apply_migration(self, version: str):
        """Применить конкретную миграцию"""
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            migration = await self.load_migration(version)
            
            logger.info(f"Применяем миграцию {version}: {migration.description}")
            await migration.up(adapter)
            
            # Записываем в таблицу миграций
            if adapter.db_type == 'sqlite':
                query = "INSERT INTO schema_migrations (version, description) VALUES (?, ?)"
            else:  # PostgreSQL
                query = "INSERT INTO schema_migrations (version, description) VALUES ($1, $2)"
            
            await adapter.execute(query, (version, migration.description))
            logger.info(f"✅ Миграция {version} применена")
            
        except Exception as e:
            logger.error(f"❌ Ошибка применения миграции {version}: {e}")
            raise
        finally:
            await adapter.disconnect()
    
    async def rollback_migration(self, version: str):
        """Откатить миграцию"""
        adapter = DatabaseAdapter(self.database_url)
        await adapter.connect()
        
        try:
            migration = await self.load_migration(version)
            
            logger.info(f"Откатываем миграцию {version}: {migration.description}")
            await migration.down(adapter)
            
            # Удаляем из таблицы миграций
            if adapter.db_type == 'sqlite':
                query = "DELETE FROM schema_migrations WHERE version = ?"
            else:  # PostgreSQL
                query = "DELETE FROM schema_migrations WHERE version = $1"
            
            await adapter.execute(query, (version,))
            logger.info(f"✅ Миграция {version} откачена")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отката миграции {version}: {e}")
            raise
        finally:
            await adapter.disconnect()
    
    async def migrate(self):
        """Применить все неприменённые миграции"""
        logger.info("🚀 Запуск системы миграций...")
        
        await self.init_migrations_table()
        
        applied_migrations = await self.get_applied_migrations()
        available_migrations = self.discover_migrations()
        
        pending_migrations = [v for v in available_migrations if v not in applied_migrations]
        
        if not pending_migrations:
            logger.info("✅ Все миграции уже применены")
            return
        
        logger.info(f"📋 Найдено {len(pending_migrations)} новых миграций")
        
        for version in pending_migrations:
            await self.apply_migration(version)
        
        logger.info(f"✅ Применено {len(pending_migrations)} миграций")
    
    async def status(self):
        """Показать статус миграций"""
        await self.init_migrations_table()
        
        applied_migrations = await self.get_applied_migrations()
        available_migrations = self.discover_migrations()
        
        print(f"\n📊 Статус миграций:")
        print(f"   Доступно: {len(available_migrations)}")
        print(f"   Применено: {len(applied_migrations)}")
        print(f"   Ожидает: {len(available_migrations) - len(applied_migrations)}")
        
        print(f"\n📋 Миграции:")
        for version in available_migrations:
            status = "✅ Применена" if version in applied_migrations else "⏳ Ожидает"
            print(f"   {version}: {status}")
    
    def create_migration(self, description: str) -> str:
        """Создать новую миграцию"""
        # Генерируем номер версии
        existing_versions = self.discover_migrations()
        if existing_versions:
            last_version = max(existing_versions)
            next_version = f"{int(last_version) + 1:03d}"
        else:
            next_version = "001"
        
        # Создаем имя файла
        safe_description = description.lower().replace(' ', '_').replace('-', '_')
        filename = f"{next_version}_{safe_description}.py"
        file_path = self.migrations_dir / filename
        
        # Создаем шаблон миграции
        template = f'''"""
Миграция {next_version}: {description}
Создана: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
from database.migration_manager import Migration
from database.db_adapter import DatabaseAdapter

class Migration{next_version}(Migration):
    def __init__(self):
        super().__init__("{next_version}", "{description}")
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        # TODO: Реализовать применение миграции
        pass
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        # TODO: Реализовать откат миграции
        pass

# Экспортируем класс для менеджера миграций
Migration = Migration{next_version}
'''
        
        file_path.write_text(template, encoding='utf-8')
        logger.info(f"✅ Создана миграция: {filename}")
        
        return filename


# Глобальная функция для автоматического запуска миграций
async def auto_migrate(database_url: str):
    """Автоматически применить все миграции при запуске приложения"""
    try:
        manager = MigrationManager(database_url)
        await manager.migrate()
    except Exception as e:
        logger.error(f"❌ Ошибка автоматических миграций: {e}")
        # Не прерываем запуск приложения из-за ошибок миграций
        pass
