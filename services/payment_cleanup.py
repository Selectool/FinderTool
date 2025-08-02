"""
Production-ready система очистки неоплаченных инвойсов
Автоматически отменяет просроченные платежи для корректной статистики
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from database.models import Database

logger = logging.getLogger(__name__)

class PaymentCleanupService:
    """Сервис для очистки просроченных платежей"""
    
    def __init__(self, db: Database):
        self.db = db
        self.cleanup_interval = 300  # 5 минут
        self.invoice_timeout = 1800  # 30 минут для оплаты инвойса
        self.running = False
    
    async def cleanup_expired_invoices(self) -> Dict[str, int]:
        """
        Очистка просроченных инвойсов
        Отменяет платежи, которые не были оплачены в течение timeout периода
        """
        try:
            import aiosqlite
            
            # Время, после которого инвойс считается просроченным
            expiry_time = datetime.now() - timedelta(seconds=self.invoice_timeout)
            
            cleanup_stats = {
                'expired_found': 0,
                'cancelled': 0,
                'errors': 0
            }
            
            async with aiosqlite.connect(self.db.db_path) as db:
                # Находим просроченные неоплаченные инвойсы
                cursor = await db.execute("""
                    SELECT payment_id, user_id, amount, created_at
                    FROM payments
                    WHERE status = 'pending' 
                    AND created_at < ?
                """, (expiry_time,))
                
                expired_payments = await cursor.fetchall()
                cleanup_stats['expired_found'] = len(expired_payments)
                
                if expired_payments:
                    logger.info(f"🧹 Найдено {len(expired_payments)} просроченных инвойсов для очистки")
                    
                    # Отменяем просроченные платежи
                    for payment in expired_payments:
                        try:
                            payment_id, user_id, amount, created_at = payment
                            
                            # Обновляем статус на cancelled
                            await db.execute("""
                                UPDATE payments 
                                SET status = 'expired', 
                                    updated_at = CURRENT_TIMESTAMP,
                                    cancellation_reason = 'Invoice expired after 30 minutes'
                                WHERE payment_id = ?
                            """, (payment_id,))
                            
                            cleanup_stats['cancelled'] += 1
                            
                            logger.info(f"❌ Отменен просроченный платеж {payment_id} пользователя {user_id} на сумму {amount/100:.2f}₽")
                            
                        except Exception as e:
                            logger.error(f"Ошибка при отмене платежа {payment_id}: {e}")
                            cleanup_stats['errors'] += 1
                    
                    await db.commit()
                    
                    if cleanup_stats['cancelled'] > 0:
                        logger.info(f"✅ Очистка завершена: отменено {cleanup_stats['cancelled']} просроченных инвойсов")
                else:
                    logger.debug("✨ Просроченных инвойсов не найдено")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке просроченных инвойсов: {e}")
            return {'expired_found': 0, 'cancelled': 0, 'errors': 1}
    
    async def cleanup_old_failed_payments(self, days_old: int = 7) -> int:
        """
        Удаление старых неуспешных платежей для оптимизации БД
        """
        try:
            import aiosqlite
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            async with aiosqlite.connect(self.db.db_path) as db:
                # Удаляем старые неуспешные платежи
                cursor = await db.execute("""
                    DELETE FROM payments
                    WHERE status IN ('expired', 'cancelled', 'failed')
                    AND created_at < ?
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                await db.commit()
                
                if deleted_count > 0:
                    logger.info(f"🗑️ Удалено {deleted_count} старых неуспешных платежей (старше {days_old} дней)")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"❌ Ошибка при удалении старых платежей: {e}")
            return 0
    
    async def get_cleanup_statistics(self) -> Dict[str, Any]:
        """Получить статистику по очистке платежей"""
        try:
            import aiosqlite
            
            stats = {
                'pending_invoices': 0,
                'expired_invoices': 0,
                'oldest_pending': None,
                'cleanup_needed': False
            }
            
            async with aiosqlite.connect(self.db.db_path) as db:
                # Количество ожидающих платежей
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM payments WHERE status = 'pending'
                """)
                row = await cursor.fetchone()
                stats['pending_invoices'] = row[0] if row else 0
                
                # Количество просроченных платежей
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM payments WHERE status = 'expired'
                """)
                row = await cursor.fetchone()
                stats['expired_invoices'] = row[0] if row else 0
                
                # Самый старый ожидающий платеж
                cursor = await db.execute("""
                    SELECT MIN(created_at) FROM payments WHERE status = 'pending'
                """)
                row = await cursor.fetchone()
                if row and row[0]:
                    stats['oldest_pending'] = row[0]
                    
                    # Проверяем, нужна ли очистка
                    oldest_time = datetime.fromisoformat(row[0])
                    if datetime.now() - oldest_time > timedelta(seconds=self.invoice_timeout):
                        stats['cleanup_needed'] = True
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка при получении статистики очистки: {e}")
            return {}
    
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

def get_cleanup_service(db: Database) -> PaymentCleanupService:
    """Получить экземпляр сервиса очистки"""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = PaymentCleanupService(db)
    return _cleanup_service

async def start_payment_cleanup(db: Database):
    """Запуск сервиса очистки платежей"""
    cleanup_service = get_cleanup_service(db)
    await cleanup_service.start_cleanup_scheduler()

def stop_payment_cleanup():
    """Остановка сервиса очистки платежей"""
    global _cleanup_service
    if _cleanup_service:
        _cleanup_service.stop_cleanup_scheduler()
