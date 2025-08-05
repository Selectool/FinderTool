"""
Миграция 009: Исправление проблем production_database_manager
Создана: 2025-08-04 23:05:00
Исправляет проблемы с первичными ключами и внешними ключами в production_database_manager
"""
from database.migration_manager import Migration
from database.db_adapter import DatabaseAdapter
import logging

logger = logging.getLogger(__name__)

class Migration009(Migration):
    def __init__(self):
        super().__init__("009", "Исправление проблем production_database_manager")
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        logger.info("🔧 Исправляем проблемы production_database_manager...")
        
        try:
            # Проверяем и исправляем таблицы, созданные production_database_manager
            await self._fix_production_tables(adapter)
            
            logger.info("✅ Проблемы production_database_manager исправлены")
            
        except Exception as e:
            logger.error(f"❌ Ошибка исправления production_database_manager: {e}")
            raise
    
    async def _fix_production_tables(self, adapter: DatabaseAdapter):
        """Исправить таблицы, созданные production_database_manager"""
        
        # Проверяем существование проблемных таблиц
        tables_to_check = ['user_requests']
        
        for table_name in tables_to_check:
            table_exists = await self._table_exists(adapter, table_name)
            if table_exists:
                logger.info(f"🔧 Исправляем таблицу {table_name}...")
                
                # Удаляем проблемную таблицу и пересоздаем с правильной схемой
                if table_name == 'user_requests':
                    await self._fix_user_requests_table(adapter)
    
    async def _fix_user_requests_table(self, adapter: DatabaseAdapter):
        """Исправить таблицу user_requests"""
        try:
            # Сначала удаляем внешние ключи, если они есть
            await adapter.execute("""
                ALTER TABLE user_requests 
                DROP CONSTRAINT IF EXISTS user_requests_user_id_fkey
            """)
            
            # Удаляем таблицу
            await adapter.execute("DROP TABLE IF EXISTS user_requests")
            
            # Пересоздаем с правильной схемой
            await adapter.execute("""
                CREATE TABLE IF NOT EXISTS user_requests (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    request_type VARCHAR(100),
                    request_data TEXT,
                    response_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processing_time FLOAT,
                    status VARCHAR(50) DEFAULT 'completed',
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            logger.info("✅ Таблица user_requests исправлена")
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка исправления user_requests: {e}")
    
    async def _table_exists(self, adapter: DatabaseAdapter, table_name: str) -> bool:
        """Проверить существование таблицы"""
        try:
            if adapter.db_type == 'postgresql':
                result = await adapter.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = $1
                    )
                """, (table_name,))
                return bool(result)
            else:  # SQLite
                result = await adapter.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table_name,))
                return result is not None
        except Exception:
            return False
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        logger.warning("⚠️ Откат миграции 009 не реализован")
        pass

# Экспортируем класс для менеджера миграций
Migration = Migration009
