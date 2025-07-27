"""
Webhook обработчики для ЮKassa
Production-ready реализация для обработки уведомлений о статусах платежей
"""
import logging
import json
import hashlib
import hmac
from typing import Dict, Any, Optional
from datetime import datetime

from database.models import Database

logger = logging.getLogger(__name__)


class YooKassaWebhookHandler:
    """Обработчик webhook уведомлений от ЮKassa"""
    
    def __init__(self, secret_key: str = None, db: Database = None):
        self.secret_key = secret_key
        self.db = db or Database()
        
        logger.info("Инициализирован YooKassaWebhookHandler")
        if secret_key:
            logger.info("✅ Секретный ключ для webhook установлен")
        else:
            logger.warning("⚠️ Секретный ключ для webhook не установлен - проверка подписи отключена")
    
    def verify_signature(self, payload: str, signature: str) -> bool:
        """Проверка подписи webhook уведомления"""
        if not self.secret_key:
            logger.warning("Секретный ключ не установлен, пропускаем проверку подписи")
            return True
        
        try:
            expected_signature = hmac.new(
                self.secret_key.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            is_valid = hmac.compare_digest(signature, expected_signature)
            
            if is_valid:
                logger.info("✅ Подпись webhook уведомления корректна")
            else:
                logger.error("❌ Неверная подпись webhook уведомления")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Ошибка при проверке подписи webhook: {e}")
            return False
    
    async def handle_payment_notification(self, notification_data: Dict[str, Any]) -> bool:
        """Обработка уведомления о платеже"""
        try:
            logger.info(f"📨 Получено webhook уведомление: {json.dumps(notification_data, ensure_ascii=False, indent=2)}")
            
            # Извлекаем данные о платеже
            event = notification_data.get('event')
            payment_object = notification_data.get('object')
            
            if not payment_object:
                logger.error("❌ Отсутствует объект платежа в уведомлении")
                return False
            
            payment_id = payment_object.get('id')
            status = payment_object.get('status')
            amount = payment_object.get('amount', {}).get('value')
            currency = payment_object.get('amount', {}).get('currency')
            metadata = payment_object.get('metadata', {})
            
            logger.info(f"Обработка платежа:")
            logger.info(f"  - Event: {event}")
            logger.info(f"  - Payment ID: {payment_id}")
            logger.info(f"  - Status: {status}")
            logger.info(f"  - Amount: {amount} {currency}")
            logger.info(f"  - Metadata: {metadata}")
            
            # Обрабатываем различные статусы платежа
            if event == 'payment.succeeded' and status == 'succeeded':
                return await self._handle_successful_payment(payment_object)
            elif event == 'payment.canceled' and status == 'canceled':
                return await self._handle_canceled_payment(payment_object)
            elif event == 'payment.waiting_for_capture':
                return await self._handle_waiting_payment(payment_object)
            else:
                logger.info(f"Неизвестный тип события: {event} со статусом {status}")
                return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке webhook уведомления: {e}")
            return False
    
    async def _handle_successful_payment(self, payment_object: Dict[str, Any]) -> bool:
        """Обработка успешного платежа"""
        try:
            payment_id = payment_object.get('id')
            amount_value = payment_object.get('amount', {}).get('value')
            metadata = payment_object.get('metadata', {})
            
            # Извлекаем наш внутренний payment_id из metadata
            internal_payment_id = metadata.get('payment_id')
            user_id = metadata.get('user_id')
            
            if not internal_payment_id:
                logger.error(f"❌ Отсутствует внутренний payment_id в metadata для платежа {payment_id}")
                return False
            
            logger.info(f"💰 Обработка успешного платежа через webhook:")
            logger.info(f"  - ЮKassa Payment ID: {payment_id}")
            logger.info(f"  - Внутренний Payment ID: {internal_payment_id}")
            logger.info(f"  - User ID: {user_id}")
            logger.info(f"  - Сумма: {amount_value}")
            
            # Завершаем платеж в нашей базе данных
            success = await self.db.complete_payment(
                payment_id=internal_payment_id,
                provider_payment_id=payment_id
            )
            
            if success:
                logger.info(f"✅ Платеж {internal_payment_id} успешно завершен через webhook")
                return True
            else:
                logger.error(f"❌ Не удалось завершить платеж {internal_payment_id} через webhook")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке успешного платежа через webhook: {e}")
            return False
    
    async def _handle_canceled_payment(self, payment_object: Dict[str, Any]) -> bool:
        """Обработка отмененного платежа"""
        try:
            payment_id = payment_object.get('id')
            metadata = payment_object.get('metadata', {})
            internal_payment_id = metadata.get('payment_id')
            
            logger.info(f"❌ Обработка отмененного платежа:")
            logger.info(f"  - ЮKassa Payment ID: {payment_id}")
            logger.info(f"  - Внутренний Payment ID: {internal_payment_id}")
            
            if internal_payment_id:
                # Обновляем статус платежа на отмененный
                await self.db.update_payment_status(internal_payment_id, 'canceled')
                logger.info(f"✅ Статус платежа {internal_payment_id} обновлен на 'canceled'")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке отмененного платежа: {e}")
            return False
    
    async def _handle_waiting_payment(self, payment_object: Dict[str, Any]) -> bool:
        """Обработка платежа в ожидании подтверждения"""
        try:
            payment_id = payment_object.get('id')
            logger.info(f"⏳ Платеж {payment_id} ожидает подтверждения")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке ожидающего платежа: {e}")
            return False


def create_webhook_handler(secret_key: str = None, db: Database = None) -> YooKassaWebhookHandler:
    """Фабричная функция для создания обработчика webhook'ов"""
    return YooKassaWebhookHandler(secret_key=secret_key, db=db)
