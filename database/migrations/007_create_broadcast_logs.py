"""
Миграция 007: Создание таблицы broadcast_logs для логирования рассылок
"""

import logging
from database.db_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)

async def migrate(adapter: DatabaseAdapter):
    """Создать таблицу broadcast_logs"""
    try:
        logger.info("Применение миграции 007: Создание таблицы broadcast_logs")
        
        # Создаем таблицу broadcast_logs
        if adapter.db_type == 'sqlite':
            create_table_query = """
                CREATE TABLE IF NOT EXISTS broadcast_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broadcast_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    error_details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (broadcast_id) REFERENCES broadcasts (id)
                )
            """
        else:  # PostgreSQL
            create_table_query = """
                CREATE TABLE IF NOT EXISTS broadcast_logs (
                    id SERIAL PRIMARY KEY,
                    broadcast_id INTEGER NOT NULL,
                    user_id BIGINT NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    message TEXT,
                    error_details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        
        await adapter.execute(create_table_query)
        logger.info("✅ Таблица broadcast_logs создана")
        
        # Создаем индексы для оптимизации
        indexes = [
            ("idx_broadcast_logs_broadcast_id", "broadcast_id"),
            ("idx_broadcast_logs_user_id", "user_id"),
            ("idx_broadcast_logs_status", "status"),
            ("idx_broadcast_logs_created_at", "created_at"),
            ("idx_broadcast_logs_broadcast_status", "broadcast_id, status")
        ]
        
        for index_name, columns in indexes:
            try:
                if adapter.db_type == 'sqlite':
                    index_query = f"""
                        CREATE INDEX IF NOT EXISTS {index_name}
                        ON broadcast_logs ({columns})
                    """
                else:  # PostgreSQL
                    index_query = f"""
                        CREATE INDEX IF NOT EXISTS {index_name}
                        ON broadcast_logs ({columns})
                    """
                
                await adapter.execute(index_query)
                logger.info(f"✅ Создан индекс {index_name}")
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка создания индекса {index_name}: {e}")
        
        # Добавляем внешний ключ для PostgreSQL (если таблица broadcasts существует)
        if adapter.db_type == 'postgresql':
            try:
                # Проверяем существование таблицы broadcasts
                check_table_query = """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'broadcasts'
                    )
                """
                result = await adapter.fetch_one(check_table_query)
                
                if result and result.get('exists', False):
                    # Добавляем внешний ключ
                    fk_query = """
                        ALTER TABLE broadcast_logs 
                        ADD CONSTRAINT fk_broadcast_logs_broadcast_id 
                        FOREIGN KEY (broadcast_id) REFERENCES broadcasts (id) 
                        ON DELETE CASCADE
                    """
                    await adapter.execute(fk_query)
                    logger.info("✅ Добавлен внешний ключ для broadcast_logs")
                    
            except Exception as e:
                logger.warning(f"⚠️ Не удалось добавить внешний ключ: {e}")
        
        logger.info("✅ Миграция 007 применена успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка применения миграции 007: {e}")
        raise

async def rollback(adapter: DatabaseAdapter):
    """Откатить миграцию 007"""
    try:
        logger.info("Откат миграции 007: Удаление таблицы broadcast_logs")
        
        # Удаляем таблицу
        await adapter.execute("DROP TABLE IF EXISTS broadcast_logs")
        logger.info("✅ Таблица broadcast_logs удалена")
        
        logger.info("✅ Откат миграции 007 выполнен успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отката миграции 007: {e}")
        raise
