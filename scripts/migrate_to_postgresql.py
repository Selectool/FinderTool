#!/usr/bin/env python3
"""
Скрипт миграции данных из SQLite в PostgreSQL
Использовать для переноса данных в продакшн
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from database.db_adapter import DatabaseAdapter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataMigrator:
    """Класс для миграции данных между базами"""
    
    def __init__(self, sqlite_url: str, postgresql_url: str):
        self.sqlite_adapter = DatabaseAdapter(sqlite_url)
        self.postgresql_adapter = DatabaseAdapter(postgresql_url)
        
    async def migrate_all_data(self):
        """Мигрировать все данные"""
        try:
            logger.info("Начинаем миграцию данных...")
            
            # Подключаемся к базам
            await self.sqlite_adapter.connect()
            await self.postgresql_adapter.connect()
            
            # Создаем таблицы в PostgreSQL
            await self.postgresql_adapter.create_tables_if_not_exist()
            
            # Мигрируем данные по таблицам
            await self.migrate_users()
            await self.migrate_requests()
            await self.migrate_payments()
            
            # Дополнительные таблицы если есть
            await self.migrate_broadcasts()
            await self.migrate_admin_users()
            
            logger.info("Миграция завершена успешно!")
            
        except Exception as e:
            logger.error(f"Ошибка миграции: {e}")
            raise
        finally:
            await self.sqlite_adapter.disconnect()
            await self.postgresql_adapter.disconnect()
    
    async def migrate_users(self):
        """Мигрировать пользователей"""
        logger.info("Мигрируем пользователей...")
        
        # Получаем всех пользователей из SQLite
        users = await self.sqlite_adapter.fetch_all("SELECT * FROM users")
        
        if not users:
            logger.info("Пользователи не найдены")
            return
            
        logger.info(f"Найдено {len(users)} пользователей")
        
        # Вставляем в PostgreSQL
        for user in users:
            try:
                await self.postgresql_adapter.execute("""
                    INSERT INTO users (
                        user_id, username, first_name, last_name, created_at,
                        requests_used, is_subscribed, subscription_end, last_request,
                        last_payment_date, payment_provider, role, blocked, bot_blocked, blocked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (user_id) DO NOTHING
                """, (
                    user['user_id'], user.get('username'), user.get('first_name'),
                    user.get('last_name'), user.get('created_at'), user.get('requests_used', 0),
                    user.get('is_subscribed', False), user.get('subscription_end'),
                    user.get('last_request'), user.get('last_payment_date'),
                    user.get('payment_provider'), user.get('role', 'user'),
                    user.get('blocked', False), user.get('bot_blocked', False),
                    user.get('blocked_at')
                ))
            except Exception as e:
                logger.error(f"Ошибка вставки пользователя {user['user_id']}: {e}")
        
        logger.info("Пользователи мигрированы")
    
    async def migrate_requests(self):
        """Мигрировать запросы"""
        logger.info("Мигрируем запросы...")
        
        try:
            requests = await self.sqlite_adapter.fetch_all("SELECT * FROM requests")
            
            if not requests:
                logger.info("Запросы не найдены")
                return
                
            logger.info(f"Найдено {len(requests)} запросов")
            
            for request in requests:
                try:
                    await self.postgresql_adapter.execute("""
                        INSERT INTO requests (user_id, channels_input, results, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (
                        request['user_id'], request.get('channels_input'),
                        request.get('results'), request.get('created_at')
                    ))
                except Exception as e:
                    logger.error(f"Ошибка вставки запроса {request.get('id')}: {e}")
            
            logger.info("Запросы мигрированы")
        except Exception as e:
            logger.warning(f"Таблица requests не найдена или пуста: {e}")
    
    async def migrate_payments(self):
        """Мигрировать платежи"""
        logger.info("Мигрируем платежи...")
        
        try:
            payments = await self.sqlite_adapter.fetch_all("SELECT * FROM payments")
            
            if not payments:
                logger.info("Платежи не найдены")
                return
                
            logger.info(f"Найдено {len(payments)} платежей")
            
            for payment in payments:
                try:
                    await self.postgresql_adapter.execute("""
                        INSERT INTO payments (
                            user_id, payment_id, provider_payment_id, amount, currency,
                            status, invoice_payload, subscription_months, created_at, completed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (payment_id) DO NOTHING
                    """, (
                        payment['user_id'], payment.get('payment_id'),
                        payment.get('provider_payment_id'), payment.get('amount'),
                        payment.get('currency', 'RUB'), payment.get('status', 'pending'),
                        payment.get('invoice_payload'), payment.get('subscription_months', 1),
                        payment.get('created_at'), payment.get('completed_at')
                    ))
                except Exception as e:
                    logger.error(f"Ошибка вставки платежа {payment.get('payment_id')}: {e}")
            
            logger.info("Платежи мигрированы")
        except Exception as e:
            logger.warning(f"Таблица payments не найдена или пуста: {e}")
    
    async def migrate_broadcasts(self):
        """Мигрировать рассылки (если есть)"""
        logger.info("Проверяем рассылки...")
        
        try:
            broadcasts = await self.sqlite_adapter.fetch_all("SELECT * FROM broadcasts LIMIT 1")
            logger.info("Таблица broadcasts найдена, но миграция не реализована")
        except Exception:
            logger.info("Таблица broadcasts не найдена")
    
    async def migrate_admin_users(self):
        """Мигрировать админ пользователей (если есть)"""
        logger.info("Проверяем админ пользователей...")
        
        try:
            admin_users = await self.sqlite_adapter.fetch_all("SELECT * FROM admin_users LIMIT 1")
            logger.info("Таблица admin_users найдена, но миграция не реализована")
        except Exception:
            logger.info("Таблица admin_users не найдена")
    
    async def export_to_json(self, output_file: str = "backup_data.json"):
        """Экспортировать данные в JSON для резервного копирования"""
        logger.info(f"Экспортируем данные в {output_file}...")
        
        await self.sqlite_adapter.connect()
        
        data = {
            'export_date': datetime.now().isoformat(),
            'users': await self.sqlite_adapter.fetch_all("SELECT * FROM users"),
            'requests': [],
            'payments': []
        }
        
        try:
            data['requests'] = await self.sqlite_adapter.fetch_all("SELECT * FROM requests")
        except Exception:
            pass
            
        try:
            data['payments'] = await self.sqlite_adapter.fetch_all("SELECT * FROM payments")
        except Exception:
            pass
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        await self.sqlite_adapter.disconnect()
        logger.info(f"Данные экспортированы в {output_file}")

async def main():
    """Основная функция"""
    # Настройки по умолчанию
    sqlite_url = "sqlite:///bot.db"
    
    # PostgreSQL URL нужно получить из переменных окружения Dokploy
    postgresql_url = os.getenv('DATABASE_URL')
    
    if not postgresql_url:
        logger.error("Переменная DATABASE_URL не установлена!")
        logger.info("Пример: DATABASE_URL=postgresql://user:password@host:5432/database")
        return
    
    # Проверяем существование SQLite файла
    sqlite_file = sqlite_url.replace('sqlite:///', '')
    if not os.path.exists(sqlite_file):
        logger.error(f"SQLite файл {sqlite_file} не найден!")
        return
    
    migrator = DataMigrator(sqlite_url, postgresql_url)
    
    # Сначала создаем резервную копию
    await migrator.export_to_json("backup_before_migration.json")
    
    # Затем мигрируем
    await migrator.migrate_all_data()

if __name__ == "__main__":
    asyncio.run(main())
