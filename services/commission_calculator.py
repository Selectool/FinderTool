#!/usr/bin/env python3
"""
Сервис расчета комиссий для платежной системы ЮKassa
Адаптировано из проекта GSpot для production-ready использования
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class PaymentMethod(Enum):
    """Методы оплаты ЮKassa"""
    BANK_CARD = "bank_card"
    YOO_MONEY = "yoo_money" 
    SBERBANK = "sberbank"
    QIWI = "qiwi"
    SBP = "sbp"  # Система быстрых платежей
    DEFAULT = "default"

class CommissionCalculator:
    """
    Калькулятор комиссий для платежной системы
    
    Принцип работы:
    - Заказчик получает полную сумму (349₽)
    - Покупатель доплачивает комиссию сверху
    - ЮKassa удерживает свою комиссию из общей суммы
    """
    
    # Комиссии ЮKassa по методам оплаты (в процентах)
    YOOKASSA_COMMISSIONS: Dict[PaymentMethod, Decimal] = {
        PaymentMethod.BANK_CARD: Decimal("3.5"),
        PaymentMethod.YOO_MONEY: Decimal("3.5"),
        PaymentMethod.SBERBANK: Decimal("3.5"),
        PaymentMethod.SBP: Decimal("0.7"),  # СБП дешевле
        PaymentMethod.QIWI: Decimal("6.0"),
        PaymentMethod.DEFAULT: Decimal("3.5")
    }
    
    # Точность расчетов (до копеек)
    DECIMAL_PLACES = Decimal("0.01")
    
    def __init__(self):
        """Инициализация калькулятора"""
        logger.info("Инициализация калькулятора комиссий")
    
    def calculate_amount_with_commission(
        self, 
        base_amount: Decimal, 
        payment_method: Optional[PaymentMethod] = None
    ) -> Decimal:
        """
        Рассчитать сумму к оплате с учетом комиссии
        
        Args:
            base_amount: Базовая сумма (которую должен получить заказчик)
            payment_method: Метод оплаты
            
        Returns:
            Сумма к оплате покупателем (базовая сумма + комиссия)
            
        Example:
            base_amount = 349₽, commission = 3.5%
            result = 349 * (1 / (1 - 0.035)) = 361.67₽
        """
        try:
            commission_percent = self._get_commission_percent(payment_method)
            
            # Формула из GSpot: amount * (1 / (1 - commission / 100))
            commission_decimal = commission_percent / Decimal("100")
            multiplier = Decimal("1") / (Decimal("1") - commission_decimal)
            
            amount_with_commission = (base_amount * multiplier).quantize(
                self.DECIMAL_PLACES, 
                rounding=ROUND_HALF_UP
            )
            
            logger.info(
                f"Расчет комиссии: базовая сумма {base_amount}₽, "
                f"метод {payment_method}, комиссия {commission_percent}%, "
                f"к доплате {amount_with_commission}₽"
            )
            
            return amount_with_commission
            
        except Exception as e:
            logger.error(f"Ошибка расчета комиссии: {e}")
            # Fallback: возвращаем базовую сумму + 3.5%
            return self._fallback_calculation(base_amount)
    
    def calculate_amount_without_commission(
        self, 
        total_amount: Decimal, 
        payment_method: Optional[PaymentMethod] = None
    ) -> Decimal:
        """
        Рассчитать базовую сумму из общей суммы с комиссией
        
        Args:
            total_amount: Общая сумма к оплате
            payment_method: Метод оплаты
            
        Returns:
            Базовая сумма без комиссии
        """
        try:
            commission_percent = self._get_commission_percent(payment_method)
            commission_decimal = commission_percent / Decimal("100")
            
            base_amount = (total_amount * (Decimal("1") - commission_decimal)).quantize(
                self.DECIMAL_PLACES,
                rounding=ROUND_HALF_UP
            )
            
            logger.info(
                f"Обратный расчет: общая сумма {total_amount}₽, "
                f"базовая сумма {base_amount}₽"
            )
            
            return base_amount
            
        except Exception as e:
            logger.error(f"Ошибка обратного расчета: {e}")
            return total_amount
    
    def get_commission_amount(
        self, 
        base_amount: Decimal, 
        payment_method: Optional[PaymentMethod] = None
    ) -> Decimal:
        """
        Получить размер комиссии в рублях
        
        Args:
            base_amount: Базовая сумма
            payment_method: Метод оплаты
            
        Returns:
            Размер комиссии в рублях
        """
        total_amount = self.calculate_amount_with_commission(base_amount, payment_method)
        commission_amount = total_amount - base_amount
        
        logger.info(f"Размер комиссии: {commission_amount}₽")
        return commission_amount
    
    def get_commission_percent(self, payment_method: Optional[PaymentMethod] = None) -> Decimal:
        """
        Получить процент комиссии для метода оплаты
        
        Args:
            payment_method: Метод оплаты
            
        Returns:
            Процент комиссии
        """
        return self._get_commission_percent(payment_method)
    
    def _get_commission_percent(self, payment_method: Optional[PaymentMethod] = None) -> Decimal:
        """Получить процент комиссии для метода оплаты"""
        if payment_method is None:
            payment_method = PaymentMethod.DEFAULT
            
        commission = self.YOOKASSA_COMMISSIONS.get(
            payment_method, 
            self.YOOKASSA_COMMISSIONS[PaymentMethod.DEFAULT]
        )
        
        logger.debug(f"Комиссия для {payment_method}: {commission}%")
        return commission
    
    def _fallback_calculation(self, base_amount: Decimal) -> Decimal:
        """Fallback расчет при ошибках"""
        fallback_commission = self.YOOKASSA_COMMISSIONS[PaymentMethod.DEFAULT]
        multiplier = Decimal("1") + (fallback_commission / Decimal("100"))
        
        result = (base_amount * multiplier).quantize(
            self.DECIMAL_PLACES,
            rounding=ROUND_HALF_UP
        )
        
        logger.warning(f"Использован fallback расчет: {result}₽")
        return result

# Глобальный экземпляр калькулятора
commission_calculator = CommissionCalculator()

def calculate_subscription_price_with_commission(
    payment_method: Optional[str] = None
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Рассчитать цену подписки с комиссией
    
    Args:
        payment_method: Метод оплаты (строка)
        
    Returns:
        Кортеж (базовая_цена, цена_с_комиссией, размер_комиссии)
    """
    base_price = Decimal("349.00")  # Цена подписки
    
    # Преобразуем строку в enum
    method = None
    if payment_method:
        try:
            method = PaymentMethod(payment_method)
        except ValueError:
            logger.warning(f"Неизвестный метод оплаты: {payment_method}")
            method = PaymentMethod.DEFAULT
    
    price_with_commission = commission_calculator.calculate_amount_with_commission(
        base_price, method
    )
    commission_amount = price_with_commission - base_price
    
    return base_price, price_with_commission, commission_amount
