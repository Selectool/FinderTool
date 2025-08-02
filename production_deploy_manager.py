#!/usr/bin/env python3
"""
Production Deploy Manager
Управление деплоями с сохранением данных
"""
import asyncio
import subprocess
import sys
import os
import time
import logging
import json
from pathlib import Path
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class ProductionDeployManager:
    """Менеджер деплоев production"""
    
    def __init__(self):
        self.backup_dir = Path("/app/data/deploy_backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    async def create_pre_deploy_backup(self):
        """Создать бэкап перед деплоем"""
        logger.info("📦 Создание бэкапа перед деплоем...")
        
        try:
            from database.db_adapter import DatabaseAdapter
            
            database_url = os.getenv('DATABASE_URL')
            adapter = DatabaseAdapter(database_url)
            await adapter.connect()
            
            # Критически важные таблицы
            critical_tables = [
                'users', 'broadcast_messages', 'admin_users', 
                'audit_logs', 'message_templates', 'scheduled_broadcasts'
            ]
            
            backup_data = {
                "timestamp": datetime.now().isoformat(),
                "deploy_type": "pre_deploy_backup",
                "tables": {}
            }
            
            for table in critical_tables:
                try:
                    # Проверяем существование таблицы
                    if adapter.db_type == 'sqlite':
                        check_query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
                    else:  # PostgreSQL
                        check_query = "SELECT table_name FROM information_schema.tables WHERE table_name = $1"
                    
                    result = await adapter.fetch_one(check_query, (table,))
                    
                    if result:
                        # Получаем все данные таблицы
                        data = await adapter.fetch_all(f"SELECT * FROM {table}")
                        
                        # Конвертируем в JSON-совместимый формат
                        table_data = []
                        if data:
                            for row in data:
                                if isinstance(row, dict):
                                    row_dict = {}
                                    for key, value in row.items():
                                        if isinstance(value, datetime):
                                            row_dict[key] = value.isoformat()
                                        else:
                                            row_dict[key] = value
                                    table_data.append(row_dict)
                                elif isinstance(row, (tuple, list)):
                                    row_list = []
                                    for value in row:
                                        if isinstance(value, datetime):
                                            row_list.append(value.isoformat())
                                        else:
                                            row_list.append(value)
                                    table_data.append(row_list)
                        
                        backup_data["tables"][table] = {
                            "count": len(table_data),
                            "data": table_data
                        }
                        
                        logger.info(f"✅ {table}: {len(table_data)} записей")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка бэкапа таблицы {table}: {e}")
            
            # Сохраняем бэкап
            backup_file = self.backup_dir / f"pre_deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_file.write_text(json.dumps(backup_data, indent=2, ensure_ascii=False))
            
            await adapter.disconnect()
            
            logger.info(f"✅ Бэкап сохранен: {backup_file}")
            return backup_file
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания бэкапа: {e}")
            return None
    
    async def apply_migrations_safely(self):
        """Безопасное применение миграций"""
        logger.info("🔧 Применение миграций...")
        
        try:
            from database.migration_manager import MigrationManager
            
            database_url = os.getenv('DATABASE_URL')
            manager = MigrationManager(database_url)
            
            # Показываем статус до миграций
            logger.info("📊 Статус миграций до применения:")
            await manager.status()
            
            # Применяем миграции
            await manager.migrate()
            
            # Показываем статус после миграций
            logger.info("📊 Статус миграций после применения:")
            await manager.status()
            
            logger.info("✅ Миграции применены успешно")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка применения миграций: {e}")
            return False
    
    def restart_services_with_supervisor(self):
        """Перезапуск сервисов через Supervisor"""
        logger.info("🔄 Перезапуск сервисов через Supervisor...")
        
        try:
            # Останавливаем все сервисы
            subprocess.run([
                "supervisorctl", "-c", "/app/supervisord_production.conf", "stop", "all"
            ], capture_output=True, timeout=30)
            
            time.sleep(5)
            
            # Запускаем все сервисы
            result = subprocess.run([
                "supervisorctl", "-c", "/app/supervisord_production.conf", "start", "all"
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                logger.info("✅ Все сервисы перезапущены")
                
                # Проверяем статус
                time.sleep(10)
                status_result = subprocess.run([
                    "supervisorctl", "-c", "/app/supervisord_production.conf", "status"
                ], capture_output=True, text=True, timeout=10)
                
                if status_result.returncode == 0:
                    logger.info("📋 Статус сервисов после перезапуска:")
                    for line in status_result.stdout.strip().split('\n'):
                        if line.strip():
                            logger.info(f"   {line}")
                
                return True
            else:
                logger.error(f"❌ Ошибка перезапуска сервисов: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка перезапуска через Supervisor: {e}")
            return False
    
    async def verify_deployment(self):
        """Проверить успешность деплоя"""
        logger.info("🔍 Проверка успешности деплоя...")
        
        checks = []
        
        # Проверка базы данных
        try:
            from database.db_adapter import DatabaseAdapter
            
            database_url = os.getenv('DATABASE_URL')
            adapter = DatabaseAdapter(database_url)
            await adapter.connect()
            
            # Проверяем критически важные таблицы
            critical_tables = ['users', 'admin_users', 'broadcast_messages']
            for table in critical_tables:
                try:
                    count = await adapter.fetch_one(f"SELECT COUNT(*) FROM {table}")
                    count_value = count[0] if count else 0
                    checks.append(f"✅ {table}: {count_value} записей")
                except Exception as e:
                    checks.append(f"❌ {table}: ошибка - {e}")
            
            await adapter.disconnect()
            
        except Exception as e:
            checks.append(f"❌ База данных: ошибка подключения - {e}")
        
        # Проверка HTTP эндпоинтов
        import httpx
        
        endpoints = [
            "http://127.0.0.1:8080/health",
            "http://127.0.0.1:8080/api/health"
        ]
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in endpoints:
                try:
                    response = await client.get(endpoint)
                    if response.status_code == 200:
                        checks.append(f"✅ {endpoint}: OK")
                    else:
                        checks.append(f"⚠️ {endpoint}: статус {response.status_code}")
                except Exception as e:
                    checks.append(f"❌ {endpoint}: ошибка - {e}")
        
        # Выводим результаты
        logger.info("📊 Результаты проверки деплоя:")
        for check in checks:
            logger.info(f"   {check}")
        
        # Определяем общий статус
        failed_checks = [check for check in checks if check.startswith("❌")]
        if failed_checks:
            logger.error(f"❌ Деплой завершился с ошибками: {len(failed_checks)} проблем")
            return False
        else:
            logger.info("✅ Деплой успешно завершен!")
            return True
    
    async def run_production_deploy(self):
        """Выполнить production деплой"""
        logger.info("🚀 Запуск Production Deploy...")
        
        deploy_start_time = datetime.now()
        
        try:
            # 1. Создаем бэкап перед деплоем
            backup_file = await self.create_pre_deploy_backup()
            if not backup_file:
                logger.error("❌ Не удалось создать бэкап - прерываем деплой")
                return False
            
            # 2. Применяем миграции
            if not await self.apply_migrations_safely():
                logger.error("❌ Ошибка применения миграций - прерываем деплой")
                return False
            
            # 3. Перезапускаем сервисы
            if not self.restart_services_with_supervisor():
                logger.error("❌ Ошибка перезапуска сервисов - прерываем деплой")
                return False
            
            # 4. Ждем инициализации сервисов
            logger.info("⏳ Ожидание инициализации сервисов...")
            await asyncio.sleep(30)
            
            # 5. Проверяем успешность деплоя
            if not await self.verify_deployment():
                logger.error("❌ Проверка деплоя не прошла")
                return False
            
            deploy_duration = datetime.now() - deploy_start_time
            
            logger.info("🎉 PRODUCTION DEPLOY ЗАВЕРШЕН УСПЕШНО!")
            logger.info(f"⏱️ Время деплоя: {deploy_duration}")
            logger.info(f"📦 Бэкап: {backup_file}")
            logger.info("🌐 Админ-панель: http://185.207.66.201:8080")
            logger.info("🔑 Логин: admin / admin123")
            logger.info("📊 Все сервисы под управлением Supervisor")
            logger.info("🔄 Данные сохранены, миграции применены")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка деплоя: {e}")
            return False

async def main():
    """Основная функция"""
    deploy_manager = ProductionDeployManager()
    success = await deploy_manager.run_production_deploy()
    
    if not success:
        logger.error("❌ Деплой завершился с ошибками")
        sys.exit(1)
    else:
        logger.info("✅ Деплой успешно завершен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Деплой прерван пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
