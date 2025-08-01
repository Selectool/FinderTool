"""
Production-ready менеджер базы данных
"""
import aiosqlite
import asyncio
import logging
import os
import shutil
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class ProductionDatabaseManager:
    """Production-ready менеджер базы данных"""
    
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # Настройки производительности
        self.connection_timeout = 30.0
        self.busy_timeout = 30000  # 30 секунд
        self.cache_size = -64000   # 64MB кэш
        
        # Метрики
        self.query_stats = {}
        self.connection_pool = []
        
    async def get_connection(self) -> aiosqlite.Connection:
        """Получить оптимизированное подключение к БД"""
        conn = await aiosqlite.connect(
            self.db_path,
            timeout=self.connection_timeout
        )
        
        # Настройки производительности
        await conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout}")
        await conn.execute(f"PRAGMA cache_size = {self.cache_size}")
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA synchronous = NORMAL")
        await conn.execute("PRAGMA temp_store = MEMORY")
        await conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
        
        return conn
    
    async def create_indexes(self):
        """Создать индексы для оптимизации производительности"""
        indexes = [
            # Пользователи
            "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(is_subscribed, subscription_end)",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            "CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(blocked, bot_blocked)",
            
            # Запросы
            "CREATE INDEX IF NOT EXISTS idx_requests_user_created ON requests(user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at)",
            
            # Платежи
            "CREATE INDEX IF NOT EXISTS idx_payments_user_status ON payments(user_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_payments_status_created ON payments(status, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_payments_provider ON payments(provider, status)",
            
            # Рассылки
            "CREATE INDEX IF NOT EXISTS idx_broadcasts_status_created ON broadcasts(status, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_broadcasts_created_by ON broadcasts(created_by, created_at)",
            
            # Админ пользователи
            "CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_admin_users_last_login ON admin_users(last_login)",
            
            # Логи аудита
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_admin_action ON audit_logs(admin_user_id, action)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)",
        ]
        
        async with await self.get_connection() as conn:
            for index_sql in indexes:
                try:
                    await conn.execute(index_sql)
                    logger.debug(f"Создан индекс: {index_sql.split('ON')[1].split('(')[0].strip()}")
                except Exception as e:
                    logger.error(f"Ошибка создания индекса: {e}")
            
            await conn.commit()
        
        logger.info("Индексы базы данных созданы/обновлены")
    
    async def analyze_database(self):
        """Анализ и оптимизация базы данных"""
        async with await self.get_connection() as conn:
            # Обновляем статистику
            await conn.execute("ANALYZE")
            
            # Очистка неиспользуемого пространства
            await conn.execute("VACUUM")
            
            logger.info("Анализ и оптимизация базы данных выполнены")
    
    async def create_backup(self, backup_name: Optional[str] = None) -> str:
        """Создать бэкап базы данных"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"bot_backup_{timestamp}.db"
        
        backup_path = self.backup_dir / backup_name
        
        try:
            # Создаем бэкап
            shutil.copy2(self.db_path, backup_path)
            
            # Проверяем целостность бэкапа
            await self.verify_backup(backup_path)
            
            logger.info(f"Бэкап создан: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Ошибка создания бэкапа: {e}")
            raise
    
    async def verify_backup(self, backup_path: Path):
        """Проверить целостность бэкапа"""
        try:
            conn = await aiosqlite.connect(str(backup_path))
            await conn.execute("PRAGMA integrity_check")
            result = await conn.fetchone()
            await conn.close()
            
            if result[0] != "ok":
                raise Exception(f"Бэкап поврежден: {result[0]}")
                
        except Exception as e:
            logger.error(f"Ошибка проверки бэкапа: {e}")
            raise
    
    async def cleanup_old_backups(self, keep_days: int = 30):
        """Очистка старых бэкапов"""
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        for backup_file in self.backup_dir.glob("bot_backup_*.db"):
            if backup_file.stat().st_mtime < cutoff_date.timestamp():
                try:
                    backup_file.unlink()
                    logger.info(f"Удален старый бэкап: {backup_file}")
                except Exception as e:
                    logger.error(f"Ошибка удаления бэкапа {backup_file}: {e}")
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Получить статистику базы данных"""
        async with await self.get_connection() as conn:
            stats = {}
            
            # Размер базы данных
            stats['file_size'] = os.path.getsize(self.db_path)
            
            # Количество записей в таблицах
            tables = ['users', 'requests', 'payments', 'broadcasts', 'admin_users']
            for table in tables:
                try:
                    cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")
                    count = await cursor.fetchone()
                    stats[f'{table}_count'] = count[0] if count else 0
                except:
                    stats[f'{table}_count'] = 0
            
            # Статистика по пользователям
            cursor = await conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN is_subscribed = 1 THEN 1 ELSE 0 END) as subscribed,
                    SUM(CASE WHEN blocked = 1 THEN 1 ELSE 0 END) as blocked
                FROM users
            """)
            user_stats = await cursor.fetchone()
            if user_stats:
                stats['users_total'] = user_stats[0]
                stats['users_subscribed'] = user_stats[1]
                stats['users_blocked'] = user_stats[2]
            
            # Статистика по платежам
            cursor = await conn.execute("""
                SELECT 
                    status,
                    COUNT(*) as count,
                    SUM(amount) as total_amount
                FROM payments 
                GROUP BY status
            """)
            payment_stats = await cursor.fetchall()
            stats['payments_by_status'] = {row[0]: {'count': row[1], 'amount': row[2]} for row in payment_stats}
            
            # Активность за последние дни
            cursor = await conn.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM requests 
                WHERE created_at >= datetime('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            activity_stats = await cursor.fetchall()
            stats['daily_activity'] = {row[0]: row[1] for row in activity_stats}
            
            return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья базы данных"""
        health = {
            'status': 'healthy',
            'checks': {},
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Проверка подключения
            async with await self.get_connection() as conn:
                await conn.execute("SELECT 1")
                health['checks']['connection'] = 'ok'
            
            # Проверка целостности
            async with await self.get_connection() as conn:
                cursor = await conn.execute("PRAGMA integrity_check")
                result = await cursor.fetchone()
                health['checks']['integrity'] = 'ok' if result[0] == 'ok' else 'error'
            
            # Проверка размера файла
            file_size = os.path.getsize(self.db_path)
            health['checks']['file_size'] = file_size
            
            # Проверка доступности записи
            async with await self.get_connection() as conn:
                await conn.execute("CREATE TEMP TABLE test_write (id INTEGER)")
                await conn.execute("DROP TABLE test_write")
                health['checks']['write_access'] = 'ok'
            
        except Exception as e:
            health['status'] = 'unhealthy'
            health['error'] = str(e)
            logger.error(f"Проблема с базой данных: {e}")
        
        return health
    
    async def optimize_for_production(self):
        """Полная оптимизация для продакшн"""
        logger.info("Начинаем оптимизацию базы данных для продакшн...")
        
        # Создаем бэкап перед оптимизацией
        backup_path = await self.create_backup("pre_optimization_backup.db")
        logger.info(f"Создан бэкап перед оптимизацией: {backup_path}")
        
        # Создаем индексы
        await self.create_indexes()
        
        # Анализируем и оптимизируем
        await self.analyze_database()
        
        # Получаем статистику
        stats = await self.get_database_stats()
        logger.info(f"Статистика БД: {json.dumps(stats, indent=2, default=str)}")
        
        logger.info("Оптимизация базы данных завершена")
        
        return stats


# Глобальный экземпляр менеджера
db_manager = ProductionDatabaseManager()


async def init_production_database():
    """Инициализация production-ready базы данных"""
    await db_manager.optimize_for_production()
    return db_manager
