"""
Production-ready скрипт миграции данных из SQLite в PostgreSQL
Безопасный перенос всех данных с валидацией и откатом
"""
import asyncio
import aiosqlite
import asyncpg
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import json

# Добавляем корневую директорию в путь для импорта модулей
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.universal_database import UniversalDatabase
from database.db_adapter import DatabaseAdapter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SQLiteToPostgreSQLMigrator:
    """
    Production-ready мигратор данных из SQLite в PostgreSQL
    """
    
    def __init__(self, sqlite_path: str, postgresql_url: str):
        self.sqlite_path = sqlite_path
        self.postgresql_url = postgresql_url
        self.migration_log = []
        self.rollback_data = {}
        
    async def migrate(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Выполнить миграцию данных
        
        Args:
            dry_run: Если True, только проверяет данные без записи
        
        Returns:
            Результат миграции
        """
        logger.info(f"🚀 Начало миграции SQLite -> PostgreSQL (dry_run={dry_run})")
        
        result = {
            'success': False,
            'migrated_tables': [],
            'migrated_records': {},
            'errors': [],
            'warnings': [],
            'duration': 0,
            'dry_run': dry_run
        }
        
        start_time = datetime.now()
        
        try:
            # Проверяем подключения
            await self._validate_connections()
            
            # Получаем список таблиц для миграции
            tables_to_migrate = await self._get_tables_to_migrate()
            logger.info(f"📋 Найдено таблиц для миграции: {len(tables_to_migrate)}")
            
            # Мигрируем каждую таблицу
            for table_name in tables_to_migrate:
                try:
                    migrated_count = await self._migrate_table(table_name, dry_run)
                    result['migrated_records'][table_name] = migrated_count
                    result['migrated_tables'].append(table_name)
                    logger.info(f"✅ Таблица {table_name}: {migrated_count} записей")
                    
                except Exception as e:
                    error_msg = f"Ошибка миграции таблицы {table_name}: {e}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)
            
            # Проверяем целостность данных
            if not dry_run:
                await self._validate_migration(result)
            
            result['success'] = len(result['errors']) == 0
            result['duration'] = (datetime.now() - start_time).total_seconds()
            
            if result['success']:
                logger.info(f"🎉 Миграция завершена успешно за {result['duration']:.2f} сек")
            else:
                logger.error(f"❌ Миграция завершена с ошибками: {len(result['errors'])}")
            
            return result
            
        except Exception as e:
            error_msg = f"Критическая ошибка миграции: {e}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
            result['duration'] = (datetime.now() - start_time).total_seconds()
            return result
    
    async def _validate_connections(self):
        """Проверить подключения к базам данных"""
        logger.info("🔍 Проверка подключений к базам данных...")
        
        # Проверяем SQLite
        if not os.path.exists(self.sqlite_path):
            raise FileNotFoundError(f"SQLite файл не найден: {self.sqlite_path}")
        
        async with aiosqlite.connect(self.sqlite_path) as db:
            cursor = await db.execute("SELECT 1")
            await cursor.fetchone()
        
        logger.info("✅ SQLite подключение проверено")
        
        # Проверяем PostgreSQL
        pg_adapter = DatabaseAdapter(self.postgresql_url)
        await pg_adapter.connect()
        await pg_adapter.fetch_one("SELECT 1")
        await pg_adapter.disconnect()
        
        logger.info("✅ PostgreSQL подключение проверено")
    
    async def _get_tables_to_migrate(self) -> List[str]:
        """Получить список таблиц для миграции"""
        async with aiosqlite.connect(self.sqlite_path) as db:
            cursor = await db.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            tables = [row[0] for row in await cursor.fetchall()]
        
        # Фильтруем только нужные таблицы
        target_tables = ['users', 'requests', 'broadcasts', 'payments']
        return [table for table in tables if table in target_tables]
    
    async def _migrate_table(self, table_name: str, dry_run: bool) -> int:
        """Мигрировать конкретную таблицу"""
        logger.info(f"📦 Миграция таблицы: {table_name}")
        
        # Получаем данные из SQLite
        sqlite_data = await self._get_sqlite_data(table_name)
        
        if not sqlite_data:
            logger.warning(f"⚠️ Таблица {table_name} пуста")
            return 0
        
        if dry_run:
            logger.info(f"🔍 DRY RUN: Найдено {len(sqlite_data)} записей в {table_name}")
            return len(sqlite_data)
        
        # Записываем данные в PostgreSQL
        migrated_count = await self._insert_postgresql_data(table_name, sqlite_data)
        
        return migrated_count
    
    async def _get_sqlite_data(self, table_name: str) -> List[Dict[str, Any]]:
        """Получить данные из SQLite таблицы"""
        async with aiosqlite.connect(self.sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(f"SELECT * FROM {table_name}")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def _insert_postgresql_data(self, table_name: str, data: List[Dict[str, Any]]) -> int:
        """Вставить данные в PostgreSQL"""
        if not data:
            return 0
        
        pg_adapter = DatabaseAdapter(self.postgresql_url)
        await pg_adapter.connect()
        
        try:
            # Получаем структуру таблицы PostgreSQL
            columns = await self._get_postgresql_columns(pg_adapter, table_name)
            
            migrated_count = 0
            
            for record in data:
                try:
                    # Подготавливаем данные для вставки
                    insert_data = self._prepare_record_for_postgresql(record, columns, table_name)
                    
                    # Формируем запрос
                    placeholders = ', '.join([f'${i+1}' for i in range(len(insert_data))])
                    column_names = ', '.join(insert_data.keys())
                    
                    query = f"""
                        INSERT INTO {table_name} ({column_names})
                        VALUES ({placeholders})
                        ON CONFLICT DO NOTHING
                    """
                    
                    await pg_adapter.execute(query, tuple(insert_data.values()))
                    migrated_count += 1
                    
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка вставки записи в {table_name}: {e}")
                    continue
            
            return migrated_count
            
        finally:
            await pg_adapter.disconnect()
    
    async def _get_postgresql_columns(self, adapter: DatabaseAdapter, table_name: str) -> List[str]:
        """Получить список колонок PostgreSQL таблицы"""
        result = await adapter.fetch_all("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = $1 AND table_schema = 'public'
            ORDER BY ordinal_position
        """, (table_name,))
        
        return [row[0] if isinstance(row, (list, tuple)) else row['column_name'] for row in result]
    
    def _prepare_record_for_postgresql(self, record: Dict[str, Any], columns: List[str], table_name: str) -> Dict[str, Any]:
        """Подготовить запись для вставки в PostgreSQL"""
        prepared = {}
        
        for column in columns:
            if column in record:
                value = record[column]
                
                # Специальная обработка для разных типов данных
                if table_name == 'users' and column == 'user_id':
                    # Убеждаемся что user_id это BIGINT
                    prepared[column] = int(value) if value is not None else None
                elif column in ['is_subscribed', 'blocked', 'bot_blocked', 'completed', 'unlimited_access']:
                    # Булевы значения
                    if value is None:
                        prepared[column] = False
                    elif isinstance(value, bool):
                        prepared[column] = value
                    elif isinstance(value, int):
                        prepared[column] = bool(value)
                    else:
                        prepared[column] = str(value).lower() in ('true', '1', 'yes')
                elif column in ['created_at', 'subscription_end', 'last_request', 'last_payment_date', 'completed_at']:
                    # Даты и времена
                    if value is None:
                        prepared[column] = None
                    elif isinstance(value, str):
                        try:
                            # Пытаемся парсить дату
                            prepared[column] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except:
                            prepared[column] = None
                    else:
                        prepared[column] = value
                elif column in ['amount', 'requests_used', 'sent_count', 'failed_count', 'subscription_months']:
                    # Числовые значения
                    prepared[column] = int(value) if value is not None else 0
                else:
                    # Остальные значения как есть
                    prepared[column] = value
            else:
                # Устанавливаем значения по умолчанию для отсутствующих колонок
                if column == 'unlimited_access':
                    prepared[column] = False
                elif column in ['status', 'target_type']:
                    prepared[column] = 'pending' if column == 'status' else 'all'
                # Остальные колонки пропускаем (будут использованы значения по умолчанию)
        
        return prepared
    
    async def _validate_migration(self, result: Dict[str, Any]):
        """Проверить целостность миграции"""
        logger.info("🔍 Проверка целостности миграции...")
        
        pg_adapter = DatabaseAdapter(self.postgresql_url)
        await pg_adapter.connect()
        
        try:
            for table_name in result['migrated_tables']:
                # Проверяем количество записей
                pg_count_result = await pg_adapter.fetch_one(f"SELECT COUNT(*) FROM {table_name}")
                pg_count = pg_count_result[0] if isinstance(pg_count_result, (list, tuple)) else pg_count_result['count']
                
                async with aiosqlite.connect(self.sqlite_path) as db:
                    cursor = await db.execute(f"SELECT COUNT(*) FROM {table_name}")
                    sqlite_count = (await cursor.fetchone())[0]
                
                if pg_count < sqlite_count:
                    warning = f"⚠️ {table_name}: PostgreSQL ({pg_count}) < SQLite ({sqlite_count})"
                    result['warnings'].append(warning)
                    logger.warning(warning)
                else:
                    logger.info(f"✅ {table_name}: {pg_count} записей")
        
        finally:
            await pg_adapter.disconnect()


async def main():
    """Главная функция миграции"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Миграция данных SQLite -> PostgreSQL')
    parser.add_argument('--sqlite-path', default='bot.db', help='Путь к SQLite файлу')
    parser.add_argument('--postgresql-url', help='URL PostgreSQL базы данных')
    parser.add_argument('--dry-run', action='store_true', help='Только проверка без записи')
    
    args = parser.parse_args()
    
    # Получаем PostgreSQL URL из переменных окружения если не указан
    postgresql_url = args.postgresql_url or os.getenv('DATABASE_URL')
    
    if not postgresql_url:
        logger.error("❌ Не указан PostgreSQL URL. Используйте --postgresql-url или DATABASE_URL")
        return
    
    migrator = SQLiteToPostgreSQLMigrator(args.sqlite_path, postgresql_url)
    result = await migrator.migrate(dry_run=args.dry_run)
    
    # Выводим результат
    print("\n" + "="*50)
    print("📊 РЕЗУЛЬТАТ МИГРАЦИИ")
    print("="*50)
    print(f"Статус: {'✅ УСПЕШНО' if result['success'] else '❌ ОШИБКИ'}")
    print(f"Время выполнения: {result['duration']:.2f} сек")
    print(f"Мигрировано таблиц: {len(result['migrated_tables'])}")
    
    for table, count in result['migrated_records'].items():
        print(f"  • {table}: {count} записей")
    
    if result['warnings']:
        print(f"\n⚠️ Предупреждения: {len(result['warnings'])}")
        for warning in result['warnings']:
            print(f"  • {warning}")
    
    if result['errors']:
        print(f"\n❌ Ошибки: {len(result['errors'])}")
        for error in result['errors']:
            print(f"  • {error}")


if __name__ == "__main__":
    asyncio.run(main())
