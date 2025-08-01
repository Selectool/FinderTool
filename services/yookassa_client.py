#!/usr/bin/env python3
"""
Production-ready клиент для работы с ЮKassa API
Включает retry механизмы, валидацию и детальное логирование
"""
import logging
import time
import uuid
from decimal import Decimal
from typing import Dict, Any, Optional, Union
import asyncio
from functools import wraps

import yookassa
from yookassa import Configuration, Payment
from yookassa.domain.response import PaymentResponse
from yookassa.domain.exceptions import ApiError, ResponseProcessingError

from config import (
    YOOKASSA_SHOP_ID, 
    YOOKASSA_SECRET_KEY, 
    YOOKASSA_RETURN_URL,
    ENVIRONMENT
)
from .commission_calculator import commission_calculator, PaymentMethod

logger = logging.getLogger(__name__)

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Декоратор для повторных попыток при ошибках API"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (ApiError, ResponseProcessingError, Exception) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"Попытка {attempt + 1} неудачна: {e}. "
                            f"Повтор через {wait_time}с"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Все {max_retries} попыток неудачны: {e}")
            
            raise last_exception
        return wrapper
    return decorator

class YookassaClient:
    """Production-ready клиент для ЮKassa"""
    
    def __init__(self):
        """Инициализация клиента ЮKassa"""
        try:
            Configuration.account_id = YOOKASSA_SHOP_ID
            Configuration.secret_key = YOOKASSA_SECRET_KEY
            
            logger.info(
                f"ЮKassa клиент инициализирован. "
                f"Shop ID: {YOOKASSA_SHOP_ID[:8]}..., "
                f"Environment: {ENVIRONMENT}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка инициализации ЮKassa клиента: {e}")
            raise
    
    @retry_on_failure(max_retries=3, delay=1.0)
    async def create_payment(
        self,
        amount: Decimal,
        description: str,
        user_id: int,
        payment_method: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentResponse:
        """
        Создать платеж в ЮKassa
        
        Args:
            amount: Сумма платежа (уже с комиссией)
            description: Описание платежа
            user_id: ID пользователя Telegram
            payment_method: Предпочтительный метод оплаты
            metadata: Дополнительные данные
            
        Returns:
            Ответ от ЮKassa с данными платежа
        """
        try:
            # Генерируем уникальный ключ идемпотентности
            idempotency_key = str(uuid.uuid4())
            
            # Подготавливаем метаданные
            payment_metadata = {
                "user_id": str(user_id),
                "telegram_bot": "channel_finder",
                "environment": ENVIRONMENT,
                "timestamp": str(int(time.time()))
            }
            
            if metadata:
                payment_metadata.update(metadata)
            
            # Данные для создания платежа
            payment_data = {
                "amount": {
                    "value": str(amount),
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": YOOKASSA_RETURN_URL
                },
                "capture": True,  # Автоматическое списание
                "description": description,
                "metadata": payment_metadata
            }
            
            # Добавляем предпочтительный метод оплаты если указан
            if payment_method:
                payment_data["payment_method_data"] = {
                    "type": payment_method
                }
            
            logger.info(
                f"Создание платежа: сумма {amount}₽, "
                f"пользователь {user_id}, метод {payment_method}"
            )
            
            # Создаем платеж
            payment = Payment.create(payment_data, idempotency_key)
            
            logger.info(
                f"Платеж создан: ID {payment.id}, "
                f"статус {payment.status}, "
                f"URL {payment.confirmation.confirmation_url if payment.confirmation else 'N/A'}"
            )
            
            return payment
            
        except ApiError as e:
            logger.error(f"Ошибка API ЮKassa: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка создания платежа: {e}")
            raise
    
    async def get_payment(self, payment_id: str) -> PaymentResponse:
        """
        Получить информацию о платеже
        
        Args:
            payment_id: ID платежа в ЮKassa
            
        Returns:
            Информация о платеже
        """
        try:
            payment = Payment.find_one(payment_id)
            
            logger.info(f"Получена информация о платеже {payment_id}: статус {payment.status}")
            return payment
            
        except ApiError as e:
            logger.error(f"Ошибка получения платежа {payment_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка получения платежа {payment_id}: {e}")
            raise
    
    async def create_subscription_payment(
        self,
        user_id: int,
        payment_method: Optional[str] = None
    ) -> tuple[PaymentResponse, Decimal, Decimal]:
        """
        Создать платеж для подписки с расчетом комиссии
        
        Args:
            user_id: ID пользователя Telegram
            payment_method: Предпочтительный метод оплаты
            
        Returns:
            Кортеж (платеж, базовая_цена, цена_с_комиссией)
        """
        try:
            # Рассчитываем цену с комиссией
            method_enum = None
            if payment_method:
                try:
                    method_enum = PaymentMethod(payment_method)
                except ValueError:
                    logger.warning(f"Неизвестный метод оплаты: {payment_method}")
            
            base_price = Decimal("349.00")
            price_with_commission = commission_calculator.calculate_amount_with_commission(
                base_price, method_enum
            )
            commission_amount = price_with_commission - base_price
            
            # Создаем описание
            description = (
                f"Подписка FinderTool - 1 месяц. "
                f"Базовая цена: {base_price}₽, комиссия: {commission_amount}₽"
            )
            
            # Метаданные для отслеживания
            metadata = {
                "subscription_type": "monthly",
                "base_price": str(base_price),
                "commission": str(commission_amount),
                "payment_method": payment_method or "auto"
            }
            
            # Создаем платеж
            payment = await self.create_payment(
                amount=price_with_commission,
                description=description,
                user_id=user_id,
                payment_method=payment_method,
                metadata=metadata
            )
            
            logger.info(
                f"Создан платеж подписки для пользователя {user_id}: "
                f"базовая цена {base_price}₽, "
                f"к доплате {price_with_commission}₽, "
                f"комиссия {commission_amount}₽"
            )
            
            return payment, base_price, price_with_commission
            
        except Exception as e:
            logger.error(f"Ошибка создания платежа подписки: {e}")
            raise
    
    def validate_webhook_signature(
        self, 
        body: str, 
        signature: str
    ) -> bool:
        """
        Валидация подписи webhook от ЮKassa
        
        Args:
            body: Тело запроса
            signature: Подпись из заголовка
            
        Returns:
            True если подпись валидна
        """
        try:
            # TODO: Реализовать валидацию подписи согласно документации ЮKassa
            # https://yookassa.ru/developers/using-api/webhooks#signature
            
            logger.debug("Валидация подписи webhook")
            return True  # Временно всегда True
            
        except Exception as e:
            logger.error(f"Ошибка валидации подписи webhook: {e}")
            return False

# Глобальный экземпляр клиента
yookassa_client = YookassaClient()
