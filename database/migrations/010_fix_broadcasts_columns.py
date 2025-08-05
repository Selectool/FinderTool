"""
Миграция 010: Исправление столбцов таблицы broadcasts
Создана: 2025-08-04 23:12:00
Добавляет недостающие столбцы в таблицу broadcasts для корректной работы рассылок
"""
from database.migration_manager import Migration
from database.db_adapter import DatabaseAdapter
import logging

logger = logging.getLogger(__name__)

class Migration010(Migration):
    def __init__(self):
        super().__init__("010", "Исправление столбцов таблицы broadcasts")
    
    async def up(self, adapter: DatabaseAdapter):
        """Применить миграцию"""
        logger.info("🔧 Исправляем столбцы таблицы broadcasts...")
        
        try:
            # Добавляем недостающие столбцы в таблицу broadcasts
            await self._add_missing_columns(adapter)
            
            logger.info("✅ Столбцы таблицы broadcasts исправлены")
            
        except Exception as e:
            logger.error(f"❌ Ошибка исправления столбцов broadcasts: {e}")
            raise
    
    async def _add_missing_columns(self, adapter: DatabaseAdapter):
        """Добавить недостающие столбцы в таблицу broadcasts"""
        
        # Список столбцов для добавления
        columns_to_add = [
            ("message_text", "TEXT"),
            ("title", "VARCHAR(255)"),
            ("status", "VARCHAR(50) DEFAULT 'pending'"),
            ("parse_mode", "VARCHAR(50) DEFAULT 'HTML'"),
            ("target_users", "VARCHAR(100) DEFAULT 'all'"),
            ("created_by", "INTEGER"),
            ("scheduled_time", "TIMESTAMP"),
            ("started_at", "TIMESTAMP"),
            ("completed_at", "TIMESTAMP"),
            ("error_message", "TEXT"),
            ("sent_count", "INTEGER DEFAULT 0"),
            ("failed_count", "INTEGER DEFAULT 0")
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                await adapter.execute(f"""
                    ALTER TABLE broadcasts 
                    ADD COLUMN {column_name} {column_def}
                """)
                logger.info(f"✅ Добавлен столбец broadcasts.{column_name}")
            except Exception as e:
                if any(phrase in str(e).lower() for phrase in ["already exists", "duplicate column", "column already exists"]):
                    logger.info(f"ℹ️ Столбец broadcasts.{column_name} уже существует")
                else:
                    logger.warning(f"⚠️ Ошибка добавления столбца broadcasts.{column_name}: {e}")
        
        # Копируем данные из старого столбца message в новый message_text (если есть)
        try:
            # Проверяем, есть ли столбец message
            if adapter.db_type == 'postgresql':
                result = await adapter.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'broadcasts' 
                    AND column_name = 'message'
                    AND table_schema = 'public'
                """)
                
                if result:
                    # Копируем данные из message в message_text
                    await adapter.execute("""
                        UPDATE broadcasts 
                        SET message_text = message 
                        WHERE message_text IS NULL AND message IS NOT NULL
                    """)
                    logger.info("✅ Данные скопированы из message в message_text")
                    
        except Exception as e:
            logger.warning(f"⚠️ Ошибка копирования данных: {e}")
        
        # Создаем индексы для оптимизации
        indexes = [
            ("idx_broadcasts_status_new", "broadcasts", "status"),
            ("idx_broadcasts_created_by_new", "broadcasts", "created_by"),
            ("idx_broadcasts_target_users_new", "broadcasts", "target_users"),
            ("idx_broadcasts_created_at_new", "broadcasts", "created_at")
        ]
        
        for index_name, table_name, column_name in indexes:
            try:
                await adapter.execute(f"""
                    CREATE INDEX IF NOT EXISTS {index_name} 
                    ON {table_name} ({column_name})
                """)
                logger.info(f"✅ Создан индекс {index_name}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка создания индекса {index_name}: {e}")
    
    async def down(self, adapter: DatabaseAdapter):
        """Откатить миграцию"""
        logger.warning("⚠️ Откат миграции 010 не реализован - может повредить данные")
        pass

# Экспортируем класс для менеджера миграций
Migration = Migration010
