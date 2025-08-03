"""
Production-ready система очистки неоплаченных инвойсов
Автоматически отменяет просроченные платежи для корректной статистики
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from database.universal_database import UniversalDatabase

logger = logging.getLogger(__name__)

class PaymentCleanupService:
    """Сервис для очистки просроченных платежей"""

    def __init__(self, db: UniversalDatabase):
        self.db = db
        self.cleanup_interval = 300  # 5 минут
        self.invoice_timeout = 1800  # 30 минут для оплаты инвойса
        self.running = False

    def _extract_value(self, result, default=0):
        """Универсальная функция для извлечения значения из результата запроса"""
        if not result:
            return default
        if hasattr(result, '__getitem__'):
            return result[0]
        elif hasattr(result, 'count'):
            return result.count
        else:
            return int(result) if result is not None else default
    
    async def cleanup_expired_invoices(self) -> Dict[str, int]:
        """
        Очистка просроченных инвойсов
        Отменяет платежи, которые не были оплачены в течение timeout периода
        """
        try:
            from database.db_adapter import DatabaseAdapter
            import os

            # Время, после которого инвойс считается просроченным
            expiry_time = datetime.now() - timedelta(seconds=self.invoice_timeout)

            cleanup_stats = {
                'expired_found': 0,
                'cancelled': 0,
                'errors': 0
            }

            # Используем адаптер базы данных для универсальной работы
            database_url = os.getenv('DATABASE_URL', 'sqlite:///bot.db')
            adapter = DatabaseAdapter(database_url)
            await adapter.connect()

            # Находим просроченные неоплаченные инвойсы
            if adapter.db_type == 'sqlite':
                expired_payments = await adapter.fetch_all("""
                    SELECT payment_id, user_id, amount, created_at
                    FROM payments
                    WHERE status = 'pending'
                    AND created_at < ?
                """, (expiry_time,))
            else:  # PostgreSQL
                expired_payments = await adapter.fetch_all("""
                    SELECT payment_id, user_id, amount, created_at
                    FROM payments
                    WHERE status = 'pending'
                    AND created_at < $1
                """, (expiry_time,))

            cleanup_stats['expired_found'] = len(expired_payments) if expired_payments else 0

            if expired_payments:
                logger.info(f"🧹 Найдено {len(expired_payments)} просроченных инвойсов для очистки")

                # Отменяем просроченные платежи
                for payment in expired_payments:
                    try:
                        # Универсальное извлечение данных из результата
                        if hasattr(payment, '__getitem__'):
                            payment_id, user_id, amount, created_at = payment[0], payment[1], payment[2], payment[3]
                        else:
                            payment_id = payment.payment_id
                            user_id = payment.user_id
                            amount = payment.amount
                            created_at = payment.created_at

                        # Обновляем статус на cancelled
                        if adapter.db_type == 'sqlite':
                            await adapter.execute("""
                                UPDATE payments
                                SET status = 'expired',
                                    updated_at = CURRENT_TIMESTAMP,
                                    cancellation_reason = 'Invoice expired after 30 minutes'
                                WHERE payment_id = ?
                            """, (payment_id,))
                        else:  # PostgreSQL
                            await adapter.execute("""
                                UPDATE payments
                                SET status = 'expired',
                                    updated_at = NOW(),
                                    cancellation_reason = 'Invoice expired after 30 minutes'
                                WHERE payment_id = $1
                            """, (payment_id,))

                        cleanup_stats['cancelled'] += 1

                        logger.info(f"❌ Отменен просроченный платеж {payment_id} пользователя {user_id} на сумму {amount/100:.2f}₽")

                    except Exception as e:
                        logger.error(f"Ошибка при отмене платежа {payment_id}: {e}")
                        cleanup_stats['errors'] += 1

                if cleanup_stats['cancelled'] > 0:
                    logger.info(f"✅ Очистка завершена: отменено {cleanup_stats['cancelled']} просроченных инвойсов")
            else:
                logger.debug("✨ Просроченных инвойсов не найдено")

        except Exception as e:
            logger.error(f"❌ Ошибка при очистке просроченных инвойсов: {e}")
            cleanup_stats = {'expired_found': 0, 'cancelled': 0, 'errors': 1}
        finally:
            await adapter.disconnect()

        return cleanup_stats
    
    async def cleanup_old_failed_payments(self, days_old: int = 7) -> int:
        """
        Удаление старых неуспешных платежей для оптимизации БД
        """
        try:
            from database.db_adapter import DatabaseAdapter
            import os

            cutoff_date = datetime.now() - timedelta(days=days_old)

            # Используем адаптер базы данных
            database_url = os.getenv('DATABASE_URL', 'sqlite:///bot.db')
            adapter = DatabaseAdapter(database_url)
            await adapter.connect()

            try:
                # Удаляем старые неуспешные платежи
                if adapter.db_type == 'sqlite':
                    result = await adapter.execute("""
                        DELETE FROM payments
                        WHERE status IN ('expired', 'cancelled', 'failed')
                        AND created_at < ?
                    """, (cutoff_date,))
                else:  # PostgreSQL
                    result = await adapter.execute("""
                        DELETE FROM payments
                        WHERE status IN ('expired', 'cancelled', 'failed')
                        AND created_at < $1
                    """, (cutoff_date,))

                deleted_count = result if result else 0

                if deleted_count > 0:
                    logger.info(f"🗑️ Удалено {deleted_count} старых неуспешных платежей (старше {days_old} дней)")

                return deleted_count

            finally:
                await adapter.disconnect()

        except Exception as e:
            logger.error(f"❌ Ошибка при удалении старых платежей: {e}")
            return 0
    
    async def get_cleanup_statistics(self) -> Dict[str, Any]:
        """Получить статистику по очистке платежей"""
        try:
            from database.db_adapter import DatabaseAdapter
            import os

            stats = {
                'pending_invoices': 0,
                'expired_invoices': 0,
                'oldest_pending': None,
                'cleanup_needed': False
            }

            # Используем адаптер базы данных
            database_url = os.getenv('DATABASE_URL', 'sqlite:///bot.db')
            adapter = DatabaseAdapter(database_url)
            await adapter.connect()

            # Количество ожидающих платежей
            row = await adapter.fetch_one("""
                SELECT COUNT(*) FROM payments WHERE status = 'pending'
            """)
            stats['pending_invoices'] = self._extract_value(row, 0)

            # Количество просроченных платежей
            row = await adapter.fetch_one("""
                SELECT COUNT(*) FROM payments WHERE status = 'expired'
            """)
            stats['expired_invoices'] = self._extract_value(row, 0)

            # Самый старый ожидающий платеж
            row = await adapter.fetch_one("""
                SELECT MIN(created_at) FROM payments WHERE status = 'pending'
            """)
            oldest_value = self._extract_value(row, None)
            if oldest_value:
                stats['oldest_pending'] = oldest_value

                # Проверяем, нужна ли очистка
                try:
                    if isinstance(oldest_value, str):
                        oldest_time = datetime.fromisoformat(oldest_value.replace('Z', '+00:00'))
                    else:
                        oldest_time = oldest_value

                    # Убираем timezone info для сравнения
                    if hasattr(oldest_time, 'replace'):
                        oldest_time = oldest_time.replace(tzinfo=None)

                    if datetime.now() - oldest_time > timedelta(seconds=self.invoice_timeout):
                        stats['cleanup_needed'] = True
                except Exception as parse_error:
                    logger.warning(f"Ошибка парсинга времени {oldest_value}: {parse_error}")
                    stats['cleanup_needed'] = False

        except Exception as e:
            import traceback
            logger.error(f"❌ Ошибка при получении статистики очистки: {e}")
            logger.error(f"Полная ошибка: {traceback.format_exc()}")
            stats = {
                'pending_invoices': 0,
                'expired_invoices': 0,
                'oldest_pending': None,
                'cleanup_needed': False
            }
        finally:
            try:
                await adapter.disconnect()
            except:
                pass

        return stats
    
    async def start_cleanup_scheduler(self):
        """Запуск планировщика очистки"""
        self.running = True
        logger.info(f"🔄 Запущен планировщик очистки платежей (интервал: {self.cleanup_interval}с, таймаут инвойса: {self.invoice_timeout}с)")
        
        while self.running:
            try:
                # Выполняем очистку просроченных инвойсов
                cleanup_stats = await self.cleanup_expired_invoices()
                
                # Раз в час удаляем старые неуспешные платежи
                current_time = datetime.now()
                if current_time.minute == 0:  # Каждый час
                    await self.cleanup_old_failed_payments()
                
                # Ждем до следующей очистки
                await asyncio.sleep(self.cleanup_interval)
                
            except asyncio.CancelledError:
                logger.info("🛑 Планировщик очистки платежей остановлен")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в планировщике очистки: {e}")
                await asyncio.sleep(60)  # Ждем минуту при ошибке
    
    def stop_cleanup_scheduler(self):
        """Остановка планировщика очистки"""
        self.running = False
        logger.info("🛑 Остановка планировщика очистки платежей...")

# Глобальный экземпляр сервиса
_cleanup_service = None

def get_cleanup_service(db: UniversalDatabase) -> PaymentCleanupService:
    """Получить экземпляр сервиса очистки"""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = PaymentCleanupService(db)
    return _cleanup_service

async def start_payment_cleanup(db: UniversalDatabase):
    """Запуск сервиса очистки платежей"""
    cleanup_service = get_cleanup_service(db)
    await cleanup_service.start_cleanup_scheduler()

def stop_payment_cleanup():
    """Остановка сервиса очистки платежей"""
    global _cleanup_service
    if _cleanup_service:
        _cleanup_service.stop_cleanup_scheduler()
