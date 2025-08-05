"""
Менеджер сброса базы данных к чистому состоянию
Исправляет проблему с неправильной статистикой платежей
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import aiosqlite
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabaseResetManager:
    """Менеджер сброса базы данных к чистому состоянию"""
    
    def __init__(self, db_path: str = "database/bot_database.db"):
        self.db_path = db_path
        self.backup_dir = "database/backups"
        
        # Создаем директории если их нет
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)
    
    async def reset_to_clean_state(self, keep_admin_users: bool = True) -> bool:
        """
        Сброс базы данных к чистому состоянию для production
        ИСПРАВЛЯЕТ проблему с неправильной статистикой платежей
        
        Args:
            keep_admin_users: Сохранить админов при сбросе
        """
        try:
            logger.info("🔄 Начинаем сброс базы данных к чистому состоянию...")
            
            # Создаем бэкап перед сбросом
            backup_path = await self.create_backup("before_reset")
            logger.info(f"📦 Создан бэкап: {backup_path}")
            
            # Сохраняем админов если нужно
            admin_users = []
            if keep_admin_users:
                admin_users = await self._get_admin_users()
                logger.info(f"👥 Найдено {len(admin_users)} админов для сохранения")
            
            # Очищаем все таблицы
            await self._clear_all_tables()
            
            # Пересоздаем структуру таблиц
            await self._recreate_tables()
            
            # Восстанавливаем админов
            if admin_users:
                await self._restore_admin_users(admin_users)
                logger.info(f"✅ Восстановлено {len(admin_users)} админов")
            
            # Инициализируем начальные данные
            await self._initialize_production_data()
            
            logger.info("✅ База данных успешно сброшена к чистому состоянию")
            logger.info("🎯 Статистика платежей теперь будет корректной - только успешные платежи")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при сбросе базы данных: {e}")
            return False
    
    async def _get_admin_users(self) -> List[Dict]:
        """Получить список админов"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT user_id, username, first_name, last_name, 
                           is_admin, is_super_admin, created_at
                    FROM users 
                    WHERE is_admin = TRUE OR is_super_admin = TRUE
                """)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка при получении админов: {e}")
            return []
    
    async def _restore_admin_users(self, admin_users: List[Dict]):
        """Восстановить админов"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                for admin in admin_users:
                    await db.execute("""
                        INSERT OR REPLACE INTO users 
                        (user_id, username, first_name, last_name, 
                         is_admin, is_super_admin, created_at, 
                         is_subscribed, subscription_end, free_requests_used)
                        VALUES (?, ?, ?, ?, ?, ?, ?, FALSE, NULL, 0)
                    """, (
                        admin['user_id'], admin['username'], admin['first_name'],
                        admin['last_name'], admin['is_admin'], admin['is_super_admin'],
                        admin['created_at']
                    ))
                await db.commit()
        except Exception as e:
            logger.error(f"Ошибка при восстановлении админов: {e}")
    
    async def _clear_all_tables(self):
        """Очистить все таблицы"""
        tables_to_clear = [
            'payments', 'user_requests', 'broadcast_messages', 
            'user_feedback', 'channel_search_cache'
        ]
        
        async with aiosqlite.connect(self.db_path) as db:
            # Очищаем пользователей (кроме админов)
            await db.execute("DELETE FROM users WHERE is_admin = FALSE AND is_super_admin = FALSE")
            
            # Очищаем остальные таблицы
            for table in tables_to_clear:
                try:
                    await db.execute(f"DELETE FROM {table}")
                    logger.debug(f"Очищена таблица: {table}")
                except Exception as e:
                    logger.warning(f"Не удалось очистить таблицу {table}: {e}")
            
            await db.commit()
            logger.info("🧹 Все таблицы очищены")
    
    async def _recreate_tables(self):
        """Пересоздать структуру таблиц"""
        try:
            from database.models import Database
            
            db = Database()
            await db.create_tables_if_not_exist()
            logger.info("✅ Структура таблиц пересоздана")
        except Exception as e:
            logger.error(f"Ошибка при пересоздании таблиц: {e}")
    
    async def _initialize_production_data(self):
        """Инициализировать начальные данные для production"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Создаем таблицу системных настроек если её нет
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS system_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Добавляем системные настройки
                await db.execute("""
                    INSERT OR REPLACE INTO system_settings (key, value, description)
                    VALUES 
                    ('database_version', '1.0.0', 'Версия базы данных'),
                    ('reset_date', ?, 'Дата последнего сброса'),
                    ('production_mode', 'true', 'Режим production'),
                    ('maintenance_mode', 'false', 'Режим обслуживания'),
                    ('payment_stats_fixed', 'true', 'Исправлена статистика платежей')
                """, (datetime.now().isoformat(),))
                
                await db.commit()
                logger.info("✅ Начальные данные инициализированы")
        except Exception as e:
            logger.error(f"Ошибка при инициализации данных: {e}")
    
    async def create_backup(self, suffix: str = None) -> str:
        """Создать бэкап базы данных"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"
            if suffix:
                backup_name += f"_{suffix}"
            backup_name += ".db"
            
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # Копируем файл базы данных
            if os.path.exists(self.db_path):
                shutil.copy2(self.db_path, backup_path)
                logger.info(f"📦 Создан бэкап: {backup_path}")
            else:
                logger.warning(f"⚠️ Файл БД не найден: {self.db_path}")
                return ""
            
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка при создании бэкапа: {e}")
            raise
    
    async def get_reset_statistics(self) -> Dict[str, Any]:
        """Получить статистику после сброса"""
        try:
            stats = {
                'database_exists': os.path.exists(self.db_path),
                'database_size_mb': 0,
                'tables_count': 0,
                'users_count': 0,
                'admin_users_count': 0,
                'payments_count': 0,
                'reset_date': None
            }
            
            if not stats['database_exists']:
                return stats
            
            # Размер базы данных
            db_size = os.path.getsize(self.db_path)
            stats['database_size_mb'] = round(db_size / (1024 * 1024), 2)
            
            async with aiosqlite.connect(self.db_path) as db:
                # Количество таблиц
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM sqlite_master WHERE type='table'
                """)
                row = await cursor.fetchone()
                stats['tables_count'] = row[0] if row else 0
                
                # Количество пользователей
                try:
                    cursor = await db.execute("SELECT COUNT(*) FROM users")
                    row = await cursor.fetchone()
                    stats['users_count'] = row[0] if row else 0
                    
                    # Количество админов
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM users 
                        WHERE is_admin = TRUE OR is_super_admin = TRUE
                    """)
                    row = await cursor.fetchone()
                    stats['admin_users_count'] = row[0] if row else 0
                except:
                    pass
                
                # Количество платежей
                try:
                    cursor = await db.execute("SELECT COUNT(*) FROM payments")
                    row = await cursor.fetchone()
                    stats['payments_count'] = row[0] if row else 0
                except:
                    pass
                
                # Дата сброса
                try:
                    cursor = await db.execute("""
                        SELECT value FROM system_settings WHERE key = 'reset_date'
                    """)
                    row = await cursor.fetchone()
                    stats['reset_date'] = row[0] if row else None
                except:
                    pass
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка при получении статистики: {e}")
            return {}

# Функция для быстрого сброса
async def reset_database_clean():
    """Быстрый сброс базы данных к чистому состоянию"""
    reset_manager = DatabaseResetManager()
    success = await reset_manager.reset_to_clean_state(keep_admin_users=True)
    
    if success:
        stats = await reset_manager.get_reset_statistics()
        logger.info("📊 Статистика после сброса:")
        logger.info(f"  - Размер БД: {stats.get('database_size_mb', 0)} MB")
        logger.info(f"  - Пользователей: {stats.get('users_count', 0)}")
        logger.info(f"  - Админов: {stats.get('admin_users_count', 0)}")
        logger.info(f"  - Платежей: {stats.get('payments_count', 0)}")
    
    return success

if __name__ == "__main__":
    # Запуск сброса из командной строки
    asyncio.run(reset_database_clean())
