#!/usr/bin/env python3
"""
Production Data Sync Service
Синхронизирует данные между локальной разработкой и production
Обеспечивает сохранность данных при деплоях
"""
import asyncio
import os
import sys
import time
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any

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
        logging.FileHandler('/app/logs/data-sync.log')
    ]
)
logger = logging.getLogger(__name__)

class ProductionDataSync:
    """Сервис синхронизации данных production"""
    
    def __init__(self):
        self.backup_dir = Path("/app/data/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.sync_interval = 300  # 5 минут
        self.backup_interval = 3600  # 1 час
        self.last_backup = None
        
        # Критически важные таблицы для бэкапа
        self.critical_tables = [
            'users',
            'broadcast_messages',
            'admin_users',
            'audit_logs',
            'message_templates',
            'scheduled_broadcasts'
        ]
    
    async def create_data_backup(self):
        """Создать бэкап критически важных данных"""
        try:
            from database.db_adapter import DatabaseAdapter
            
            database_url = os.getenv('DATABASE_URL')
            adapter = DatabaseAdapter(database_url)
            await adapter.connect()
            
            backup_data = {
                "timestamp": datetime.now().isoformat(),
                "database_type": adapter.db_type,
                "tables": {}
            }
            
            logger.info("📦 Создание бэкапа критически важных данных...")
            
            for table in self.critical_tables:
                try:
                    # Проверяем существование таблицы
                    if adapter.db_type == 'sqlite':
                        check_query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
                    else:  # PostgreSQL
                        check_query = "SELECT table_name FROM information_schema.tables WHERE table_name = $1"
                    
                    result = await adapter.fetch_one(check_query, (table,))
                    
                    if result:
                        # Получаем данные таблицы
                        data = await adapter.fetch_all(f"SELECT * FROM {table}")
                        
                        # Конвертируем в JSON-совместимый формат
                        table_data = []
                        if data:
                            for row in data:
                                if isinstance(row, dict):
                                    # Конвертируем datetime объекты в строки
                                    row_dict = {}
                                    for key, value in row.items():
                                        if isinstance(value, datetime):
                                            row_dict[key] = value.isoformat()
                                        else:
                                            row_dict[key] = value
                                    table_data.append(row_dict)
                                elif isinstance(row, (tuple, list)):
                                    # Если row это tuple/list, конвертируем в список
                                    row_list = []
                                    for value in row:
                                        if isinstance(value, datetime):
                                            row_list.append(value.isoformat())
                                        else:
                                            row_list.append(value)
                                    table_data.append(row_list)
                                else:
                                    table_data.append(str(row))
                        
                        backup_data["tables"][table] = {
                            "count": len(table_data),
                            "data": table_data[:1000]  # Ограничиваем размер бэкапа
                        }
                        
                        logger.info(f"✅ {table}: {len(table_data)} записей")
                    else:
                        logger.warning(f"⚠️ Таблица {table} не найдена")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка бэкапа таблицы {table}: {e}")
            
            # Сохраняем бэкап
            backup_file = self.backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_file.write_text(json.dumps(backup_data, indent=2, ensure_ascii=False))
            
            # Очищаем старые бэкапы (оставляем последние 10)
            await self.cleanup_old_backups()
            
            await adapter.disconnect()
            
            self.last_backup = datetime.now()
            logger.info(f"✅ Бэкап сохранен: {backup_file}")
            
            return backup_file
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания бэкапа: {e}")
            return None
    
    async def cleanup_old_backups(self):
        """Очистить старые бэкапы"""
        try:
            backup_files = sorted(self.backup_dir.glob("backup_*.json"))
            
            # Оставляем последние 10 бэкапов
            if len(backup_files) > 10:
                for old_backup in backup_files[:-10]:
                    old_backup.unlink()
                    logger.info(f"🗑️ Удален старый бэкап: {old_backup.name}")
                    
        except Exception as e:
            logger.error(f"Ошибка очистки бэкапов: {e}")
    
    async def monitor_data_integrity(self):
        """Мониторинг целостности данных"""
        try:
            from database.db_adapter import DatabaseAdapter
            
            database_url = os.getenv('DATABASE_URL')
            adapter = DatabaseAdapter(database_url)
            await adapter.connect()
            
            integrity_report = {
                "timestamp": datetime.now().isoformat(),
                "status": "healthy",
                "issues": []
            }
            
            # Проверяем критически важные таблицы
            for table in self.critical_tables:
                try:
                    count = await adapter.fetch_one(f"SELECT COUNT(*) FROM {table}")
                    count_value = count[0] if count else 0
                    
                    if table == 'admin_users' and count_value == 0:
                        integrity_report["issues"].append(f"Таблица {table} пуста - критическая проблема!")
                        integrity_report["status"] = "critical"
                    
                    logger.debug(f"📊 {table}: {count_value} записей")
                    
                except Exception as e:
                    integrity_report["issues"].append(f"Ошибка проверки {table}: {str(e)}")
                    integrity_report["status"] = "warning"
            
            await adapter.disconnect()
            
            if integrity_report["status"] != "healthy":
                logger.warning(f"⚠️ Проблемы с целостностью данных: {integrity_report['issues']}")
            
            return integrity_report
            
        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга целостности: {e}")
            return {"status": "error", "error": str(e)}
    
    async def sync_critical_data(self):
        """Синхронизация критически важных данных"""
        try:
            # Проверяем флаг перезагрузки
            restart_flag = Path("/app/data/restart_required.flag")
            
            if restart_flag.exists():
                logger.info("🔄 Обнаружен флаг перезагрузки - создаем экстренный бэкап")
                await self.create_data_backup()
                restart_flag.unlink()  # Удаляем флаг
            
            # Регулярный мониторинг
            integrity = await self.monitor_data_integrity()
            
            if integrity["status"] == "critical":
                logger.error("🚨 КРИТИЧЕСКАЯ ПРОБЛЕМА с данными!")
                await self.create_data_backup()
            
            # Регулярный бэкап
            if (self.last_backup is None or 
                datetime.now() - self.last_backup > timedelta(seconds=self.backup_interval)):
                await self.create_data_backup()
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации данных: {e}")
    
    async def run(self):
        """Основной цикл сервиса синхронизации"""
        logger.info("🔄 Запуск Production Data Sync Service...")
        logger.info(f"📁 Директория бэкапов: {self.backup_dir}")
        logger.info(f"⏱️ Интервал синхронизации: {self.sync_interval} секунд")
        logger.info(f"💾 Интервал бэкапа: {self.backup_interval} секунд")
        
        # Первоначальная синхронизация
        await self.sync_critical_data()
        
        while True:
            try:
                await asyncio.sleep(self.sync_interval)
                await self.sync_critical_data()
                
            except KeyboardInterrupt:
                logger.info("👋 Получен сигнал остановки")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле синхронизации: {e}")
                await asyncio.sleep(self.sync_interval)

if __name__ == "__main__":
    try:
        sync_service = ProductionDataSync()
        asyncio.run(sync_service.run())
    except KeyboardInterrupt:
        logger.info("👋 Data Sync Service остановлен")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
