#!/usr/bin/env python3
"""
Скрипт для исправления типов данных user_id с INTEGER на BIGINT
Исправляет проблему "value out of int32 range" для больших Telegram user_id
"""
import asyncio
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent))

from database.universal_database import UniversalDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BigIntFixer:
    """Класс для исправления типов данных user_id"""
    
    def __init__(self):
        self.db = UniversalDatabase()
        
    async def fix_all_bigint_issues(self):
        """Исправить все проблемы с BIGINT"""
        try:
            logger.info("🔧 Начинаем исправление типов данных user_id...")
            
            await self.db.adapter.connect()
            
            # Исправляем таблицу broadcasts
            await self.fix_broadcasts_table()
            
            # Исправляем таблицу scheduled_broadcasts
            await self.fix_scheduled_broadcasts_table()
            
            # Исправляем таблицу broadcast_logs (уже должна быть BIGINT)
            await self.check_broadcast_logs_table()
            
            # Проверяем таблицу users
            await self.check_users_table()
            
            await self.db.adapter.disconnect()
            logger.info("✅ Исправление типов данных завершено!")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при исправлении типов данных: {e}")
            import traceback
            traceback.print_exc()
            
    async def fix_broadcasts_table(self):
        """Исправить таблицу broadcasts"""
        logger.info("📢 Исправляем таблицу broadcasts...")
        
        try:
            # Изменяем тип created_by на BIGINT
            await self.db.adapter.execute("""
                ALTER TABLE broadcasts 
                ALTER COLUMN created_by TYPE BIGINT
            """)
            logger.info("✅ Поле created_by в broadcasts изменено на BIGINT")
        except Exception as e:
            if "does not exist" in str(e).lower():
                logger.info("ℹ️ Поле created_by не существует в broadcasts")
            elif "already" in str(e).lower() or "bigint" in str(e).lower():
                logger.info("ℹ️ Поле created_by уже имеет тип BIGINT")
            else:
                logger.warning(f"⚠️ Ошибка изменения created_by в broadcasts: {e}")
                
    async def fix_scheduled_broadcasts_table(self):
        """Исправить таблицу scheduled_broadcasts"""
        logger.info("📅 Исправляем таблицу scheduled_broadcasts...")
        
        try:
            # Изменяем тип created_by на BIGINT
            await self.db.adapter.execute("""
                ALTER TABLE scheduled_broadcasts 
                ALTER COLUMN created_by TYPE BIGINT
            """)
            logger.info("✅ Поле created_by в scheduled_broadcasts изменено на BIGINT")
        except Exception as e:
            if "does not exist" in str(e).lower():
                logger.info("ℹ️ Поле created_by не существует в scheduled_broadcasts")
            elif "already" in str(e).lower() or "bigint" in str(e).lower():
                logger.info("ℹ️ Поле created_by уже имеет тип BIGINT")
            else:
                logger.warning(f"⚠️ Ошибка изменения created_by в scheduled_broadcasts: {e}")
                
    async def check_broadcast_logs_table(self):
        """Проверить таблицу broadcast_logs"""
        logger.info("📝 Проверяем таблицу broadcast_logs...")
        
        try:
            # Проверяем тип user_id
            result = await self.db.adapter.fetch_one("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'broadcast_logs' 
                AND column_name = 'user_id'
            """)
            
            if result:
                data_type = result.get('data_type')
                logger.info(f"Тип user_id в broadcast_logs: {data_type}")
                if data_type != 'bigint':
                    await self.db.adapter.execute("""
                        ALTER TABLE broadcast_logs 
                        ALTER COLUMN user_id TYPE BIGINT
                    """)
                    logger.info("✅ Поле user_id в broadcast_logs изменено на BIGINT")
            else:
                logger.info("ℹ️ Таблица broadcast_logs не найдена или поле user_id не существует")
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки broadcast_logs: {e}")
            
    async def check_users_table(self):
        """Проверить таблицу users"""
        logger.info("👥 Проверяем таблицу users...")
        
        try:
            # Проверяем тип user_id
            result = await self.db.adapter.fetch_one("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name = 'user_id'
            """)
            
            if result:
                data_type = result.get('data_type')
                logger.info(f"Тип user_id в users: {data_type}")
                if data_type != 'bigint':
                    await self.db.adapter.execute("""
                        ALTER TABLE users 
                        ALTER COLUMN user_id TYPE BIGINT
                    """)
                    logger.info("✅ Поле user_id в users изменено на BIGINT")
            else:
                logger.info("ℹ️ Таблица users не найдена или поле user_id не существует")
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки users: {e}")
            
    async def test_bigint_fix(self):
        """Тестировать исправление BIGINT"""
        logger.info("🧪 Тестируем исправление BIGINT...")
        
        try:
            # Тестируем создание рассылки с большим user_id
            test_user_id = 5699315855  # Проблемный user_id
            
            broadcast_id = await self.db.create_broadcast(
                title="Тест BIGINT",
                message_text="Тестовое сообщение",
                target_users="all",
                created_by=test_user_id
            )
            
            if broadcast_id:
                logger.info(f"✅ Тест успешен! Создана рассылка {broadcast_id} с user_id {test_user_id}")
                
                # Удаляем тестовую рассылку
                await self.db.adapter.execute("DELETE FROM broadcasts WHERE id = $1", broadcast_id)
                logger.info("🗑️ Тестовая рассылка удалена")
            else:
                logger.warning("⚠️ Не удалось создать тестовую рассылку")
                
        except Exception as e:
            logger.error(f"❌ Тест не прошел: {e}")

async def main():
    """Главная функция"""
    print("🚀 ИСПРАВЛЕНИЕ ТИПОВ ДАННЫХ USER_ID")
    print("=" * 50)
    
    fixer = BigIntFixer()
    await fixer.fix_all_bigint_issues()
    
    # Тестируем исправление
    await fixer.test_bigint_fix()
    
    print("\n🎉 Готово! Теперь можно создавать рассылки с большими user_id")
    print("Перезапустите бота и админ-панель для применения изменений")

if __name__ == "__main__":
    asyncio.run(main())
