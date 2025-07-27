"""
Webhook обработчики для ЮKassa
Production-ready реализация для обработки уведомлений о статусах платежей
Включает валидацию подписи, расчет комиссий и детальное логирование
"""
import logging
import json
import hashlib
import hmac
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

from database.models import Database
from .yookassa_client import yookassa_client
from .commission_calculator import commission_calculator

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
        """Обработка успешного платежа с учетом комиссий"""
        try:
            payment_id = payment_object.get('id')
            amount_data = payment_object.get('amount', {})
            amount_value = Decimal(str(amount_data.get('value', '0')))
            income_amount_data = payment_object.get('income_amount', {})
            income_amount = Decimal(str(income_amount_data.get('value', '0'))) if income_amount_data else amount_value

            metadata = payment_object.get('metadata', {})
            payment_method = payment_object.get('payment_method', {}).get('type', 'unknown')

            # Извлекаем данные из metadata
            user_id = metadata.get('user_id')
            base_price = Decimal(str(metadata.get('base_price', '349')))
            commission = Decimal(str(metadata.get('commission', '0')))

            logger.info(f"💰 Обработка успешного платежа через webhook:")
            logger.info(f"  - ЮKassa Payment ID: {payment_id}")
            logger.info(f"  - User ID: {user_id}")
            logger.info(f"  - Общая сумма: {amount_value} ₽")
            logger.info(f"  - Получено (после комиссии ЮKassa): {income_amount} ₽")
            logger.info(f"  - Базовая цена: {base_price} ₽")
            logger.info(f"  - Наша комиссия: {commission} ₽")
            logger.info(f"  - Метод оплаты: {payment_method}")

            # Проверяем корректность сумм
            expected_total = commission_calculator.calculate_amount_with_commission(
                base_price,
                payment_method if payment_method != 'unknown' else None
            )

            if abs(amount_value - expected_total) > Decimal('0.01'):
                logger.warning(
                    f"⚠️ Несоответствие сумм: ожидалось {expected_total}₽, "
                    f"получено {amount_value}₽"
                )

            # Проверяем, что заказчик получает полную базовую сумму
            if income_amount >= base_price:
                logger.info(f"✅ Заказчик получает полную сумму: {income_amount}₽ >= {base_price}₽")
            else:
                logger.warning(
                    f"⚠️ Заказчик получает меньше базовой суммы: {income_amount}₽ < {base_price}₽"
                )

            # Активируем подписку пользователя
            if user_id:
                user_id_int = int(user_id)
                success = await self.db.activate_subscription(
                    user_id=user_id_int,
                    months=1,
                    payment_id=payment_id,
                    amount_paid=float(amount_value),
                    income_amount=float(income_amount)
                )

                if success:
                    logger.info(f"✅ Подписка активирована для пользователя {user_id_int}")

                    # Дополнительное логирование для мониторинга
                    logger.info(
                        f"📊 Статистика платежа: "
                        f"пользователь={user_id_int}, "
                        f"заплатил={amount_value}₽, "
                        f"получили={income_amount}₽, "
                        f"комиссия_юкасса={amount_value - income_amount}₽, "
                        f"наша_комиссия={commission}₽"
                    )

                    return True
                else:
                    logger.error(f"❌ Не удалось активировать подписку для пользователя {user_id_int}")
                    return False
            else:
                logger.error(f"❌ Отсутствует user_id в metadata для платежа {payment_id}")
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
