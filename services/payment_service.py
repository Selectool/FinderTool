"""
Сервис для работы с платежами ЮKassa
Production-ready реализация с детальным логированием и обработкой ошибок
Включает расчет комиссий и интеграцию с ЮKassa API
"""
import uuid
import logging
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from decimal import Decimal

from aiogram.types import LabeledPrice, PreCheckoutQuery, SuccessfulPayment
from database.universal_database import UniversalDatabase
from .commission_calculator import calculate_subscription_price_with_commission, PaymentMethod
from .yookassa_client import yookassa_client

logger = logging.getLogger(__name__)


class YooKassaPaymentService:
    """Сервис для работы с платежами через ЮKassa"""

    def __init__(self, provider_token: str, currency: str = "RUB",
                 provider_data: str = None, db: UniversalDatabase = None):
        self.provider_token = provider_token
        self.currency = currency
        self.provider_data = provider_data
        self.db = db or UniversalDatabase()

        # Проверяем режим работы (TEST или LIVE) с поддержкой современных форматов
        self.is_test_mode = ":TEST:" in provider_token or provider_token.startswith("test_")

        # Валидация токена
        self._validate_token()

        logger.info(f"Инициализирован YooKassaPaymentService в режиме: {'TEST' if self.is_test_mode else 'LIVE'}")
        logger.info(f"Токен: {provider_token[:20]}...{provider_token[-10:]}")
        logger.info(f"Валюта: {currency}")

        # Дополнительное логирование для продакшн
        if not self.is_test_mode:
            logger.warning("⚠️ ВНИМАНИЕ: Работа в ПРОДАКШН режиме с реальными платежами!")
        else:
            logger.info("🧪 Работа в тестовом режиме")

    def _validate_token(self):
        """Валидация токена ЮKassa с поддержкой современных форматов"""
        if not self.provider_token:
            raise ValueError("Токен ЮKassa не может быть пустым")

        # Проверка тестового токена
        if self.is_test_mode:
            if not (":TEST:" in self.provider_token or self.provider_token.startswith("test_")):
                raise ValueError("Тестовый токен должен содержать ':TEST:' или начинаться с 'test_'")

        # Проверка продакшн токена
        if not self.is_test_mode:
            if not (":LIVE:" in self.provider_token or self.provider_token.startswith("live_")):
                raise ValueError("Продакшн токен должен содержать ':LIVE:' или начинаться с 'live_'")

        logger.info("✅ Токен ЮKassa прошел валидацию")

    def generate_payment_id(self) -> str:
        """Генерировать уникальный ID платежа"""
        return str(uuid.uuid4())

    async def create_invoice_data(self, user_id: int, amount: Optional[int] = None,
                                description: str = "Подписка FinderTool",
                                subscription_months: int = 1,
                                payment_method: Optional[str] = None) -> Dict[str, Any]:
        """
        Создать данные для инвойса с расчетом комиссии

        Args:
            user_id: ID пользователя
            amount: Сумма в копейках (если не указана, рассчитывается автоматически)
            description: Описание платежа
            subscription_months: Количество месяцев подписки
            payment_method: Предпочтительный метод оплаты
        """

        try:
            # Валидация входных данных
            if subscription_months <= 0:
                raise ValueError(f"Количество месяцев должно быть положительным: {subscription_months}")

            # Рассчитываем цену с комиссией
            base_price, price_with_commission, commission_amount = calculate_subscription_price_with_commission(
                payment_method
            )

            # Если amount не указан, используем рассчитанную цену
            if amount is None:
                amount = int(price_with_commission * 100)  # Конвертируем в копейки

            # Валидация суммы
            if amount <= 0:
                raise ValueError(f"Сумма платежа должна быть положительной: {amount}")

            # Генерируем уникальный payload для платежа
            payment_id = self.generate_payment_id()
            payload = f"subscription_{subscription_months}m_{payment_id}"

            logger.info(f"Создание платежа для пользователя {user_id}:")
            logger.info(f"  - Базовая цена: {base_price} ₽")
            logger.info(f"  - Комиссия: {commission_amount} ₽")
            logger.info(f"  - К доплате: {price_with_commission} ₽")
            logger.info(f"  - Сумма в копейках: {amount}")
            logger.info(f"  - Метод оплаты: {payment_method or 'auto'}")
            logger.info(f"  - Месяцев: {subscription_months}")
            logger.info(f"  - Payment ID: {payment_id}")
            logger.info(f"  - Payload: {payload}")

            # Сохраняем платеж в базу данных
            await self.db.create_payment(
                user_id=user_id,
                amount=amount,
                currency=self.currency,
                payment_id=payment_id,
                invoice_payload=payload,
                subscription_months=subscription_months
            )

            logger.info(f"✅ Платеж {payment_id} сохранен в базу данных")

            # Создаем описание с информацией о комиссии
            detailed_description = (
                f"{description}\n"
                f"Базовая цена: {base_price} ₽\n"
                f"Комиссия платежной системы: {commission_amount} ₽"
            )

            # Создаем массив цен для Telegram API (в копейках)
            prices = [LabeledPrice(label=description, amount=amount)]

            invoice_data = {
                "title": "Подписка FinderTool",
                "description": detailed_description,
                "payload": payload,
                "provider_token": self.provider_token,
                "currency": self.currency,
                "prices": prices,
                "need_phone_number": False,
                "send_phone_number_to_provider": False,
                "provider_data": self.provider_data
            }

            # Логируем данные инвойса (без токена и с безопасной сериализацией)
            safe_invoice_data = {k: v for k, v in invoice_data.items() if k not in ["provider_token", "prices"]}
            safe_invoice_data["prices_info"] = f"{len(invoice_data['prices'])} позиций, общая сумма: {amount} копеек"
            safe_invoice_data["commission_info"] = f"Базовая цена: {base_price}₽, комиссия: {commission_amount}₽"
            logger.info(f"Данные инвойса: {json.dumps(safe_invoice_data, ensure_ascii=False, indent=2)}")

            return invoice_data

        except Exception as e:
            logger.error(f"Ошибка при создании инвойса для пользователя {user_id}: {e}")
            raise

    async def process_pre_checkout(self, pre_checkout_query: PreCheckoutQuery) -> bool:
        """Обработать предварительную проверку платежа с детальным логированием"""
        try:
            payload = pre_checkout_query.invoice_payload
            user_id = pre_checkout_query.from_user.id
            total_amount = pre_checkout_query.total_amount
            currency = pre_checkout_query.currency

            logger.info(f"🔍 Предварительная проверка платежа:")
            logger.info(f"  - Пользователь: {user_id}")
            logger.info(f"  - Payload: {payload}")
            logger.info(f"  - Сумма: {total_amount} копеек ({total_amount/100:.2f} ₽)")
            logger.info(f"  - Валюта: {currency}")

            # Проверяем, что платеж существует в базе данных
            if payload.startswith("subscription_"):
                # Извлекаем payment_id из payload
                parts = payload.split("_")
                if len(parts) >= 3:
                    payment_id = "_".join(parts[2:])  # Восстанавливаем UUID
                    logger.info(f"  - Payment ID: {payment_id}")

                    payment = await self.db.get_payment(payment_id=payment_id)

                    if payment and payment['status'] == 'pending':
                        # Дополнительные проверки
                        if payment['user_id'] != user_id:
                            logger.error(f"❌ Платеж {payment_id} не принадлежит пользователю {user_id}")
                            return False

                        if payment['amount'] != total_amount:
                            logger.error(f"❌ Несоответствие суммы: ожидалось {payment['amount']}, получено {total_amount}")
                            return False

                        logger.info(f"✅ Платеж {payment_id} прошел предварительную проверку")
                        return True
                    else:
                        logger.error(f"❌ Платеж {payment_id} не найден или имеет неверный статус")
                        return False

            logger.error(f"❌ Неверный формат payload: {payload}")
            return False

        except Exception as e:
            logger.error(f"❌ Ошибка при предварительной проверке платежа: {e}")
            return False

    async def process_successful_payment(self, successful_payment: SuccessfulPayment, user_id: int) -> bool:
        """Обработать успешный платеж с детальным логированием"""
        try:
            payload = successful_payment.invoice_payload
            total_amount = successful_payment.total_amount
            currency = successful_payment.currency
            provider_payment_charge_id = successful_payment.provider_payment_charge_id

            logger.info(f"💰 Обработка успешного платежа:")
            logger.info(f"  - Пользователь: {user_id}")
            logger.info(f"  - Payload: {payload}")
            logger.info(f"  - Сумма: {total_amount} копеек ({total_amount/100:.2f} ₽)")
            logger.info(f"  - Валюта: {currency}")
            logger.info(f"  - Charge ID: {provider_payment_charge_id}")

            if payload.startswith("subscription_"):
                # Извлекаем payment_id из payload
                parts = payload.split("_")
                if len(parts) >= 3:
                    payment_id = "_".join(parts[2:])  # Восстанавливаем UUID
                    logger.info(f"  - Payment ID: {payment_id}")

                    # Завершаем платеж и активируем подписку
                    success = await self.db.complete_payment(
                        payment_id=payment_id,
                        provider_payment_id=provider_payment_charge_id
                    )

                    if success:
                        logger.info(f"✅ Платеж {payment_id} успешно завершен, подписка активирована для пользователя {user_id}")

                        # Дополнительная проверка активации подписки
                        is_subscribed = await self.db.check_subscription(user_id)
                        if is_subscribed:
                            logger.info(f"✅ Подписка пользователя {user_id} подтверждена")
                        else:
                            logger.error(f"❌ Подписка пользователя {user_id} не активирована!")

                        return True
                    else:
                        logger.error(f"❌ Не удалось завершить платеж {payment_id}")
                        return False
                else:
                    logger.error(f"❌ Неверный формат payload: {payload}")
                    return False

            logger.error(f"❌ Неверный формат payload при успешном платеже: {payload}")
            return False

        except Exception as e:
            logger.error(f"❌ Ошибка при обработке успешного платежа: {e}")
            return False

    async def create_yookassa_payment(
        self,
        user_id: int,
        payment_method: Optional[str] = None
    ) -> Tuple[str, Decimal, Decimal]:
        """
        Создать платеж через ЮKassa API с расчетом комиссии

        Args:
            user_id: ID пользователя
            payment_method: Предпочтительный метод оплаты

        Returns:
            Кортеж (payment_url, базовая_цена, цена_с_комиссией)
        """
        try:
            logger.info(f"Создание платежа ЮKassa для пользователя {user_id}")

            # Создаем платеж через ЮKassa клиент
            payment, base_price, price_with_commission = await yookassa_client.create_subscription_payment(
                user_id=user_id,
                payment_method=payment_method
            )

            # Сохраняем платеж в нашу БД
            payment_id = self.generate_payment_id()
            payload = f"yookassa_subscription_{payment_id}"

            await self.db.create_payment(
                user_id=user_id,
                amount=int(price_with_commission * 100),  # В копейках
                currency="RUB",
                payment_id=payment_id,
                invoice_payload=payload,
                subscription_months=1
            )

            logger.info(
                f"✅ Платеж ЮKassa создан: ID {payment.id}, "
                f"URL {payment.confirmation.confirmation_url}, "
                f"сумма {price_with_commission}₽"
            )

            return payment.confirmation.confirmation_url, base_price, price_with_commission

        except Exception as e:
            logger.error(f"Ошибка создания платежа ЮKassa для пользователя {user_id}: {e}")
            raise

    async def get_payment_info(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о платеже"""
        try:
            payment = await self.db.get_payment(payment_id=payment_id)
            return payment
        except Exception as e:
            logger.error(f"Ошибка при получении информации о платеже {payment_id}: {e}")
            return None

    async def get_user_payments_history(self, user_id: int) -> list:
        """Получить историю платежей пользователя"""
        try:
            payments = await self.db.get_user_payments(user_id)
            return payments
        except Exception as e:
            logger.error(f"Ошибка при получении истории платежей пользователя {user_id}: {e}")
            return []

    def get_test_card_info(self) -> str:
        """Получить информацию о тестовой карте"""
        if self.is_test_mode:
            return ("Для тестовой оплаты используйте данные:\n"
                   "💳 Карта: 1111 1111 1111 1026\n"
                   "📅 Срок: 12/22\n"
                   "🔐 CVC: 000")
        return ""

    def format_amount_for_display(self, amount_in_kopecks: int) -> str:
        """Форматировать сумму для отображения пользователю"""
        rubles = amount_in_kopecks // 100
        return f"{rubles} ₽"

    async def cancel_payment(self, payment_id: str) -> bool:
        """Отменить платеж"""
        try:
            await self.db.update_payment_status(payment_id, "cancelled")
            logger.info(f"Платеж {payment_id} отменен")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отмене платежа {payment_id}: {e}")
            return False

    async def get_payment_statistics(self) -> dict:
        """
        Получить корректную статистику платежей
        ИСПРАВЛЕНО: Считаем только успешные платежи, а не созданные инвойсы
        """
        try:
            from datetime import datetime, timedelta
            import aiosqlite

            stats = {
                'today': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
                'week': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
                'month': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
                'total': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0}
            }

            async with aiosqlite.connect(self.db.db_path) as db:
                # Статистика за сегодня - ТОЛЬКО успешные платежи
                today = datetime.now().date()
                cursor = await db.execute("""
                    SELECT
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_count,
                        SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END) as successful_amount,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                        COUNT(CASE WHEN status IN ('cancelled', 'failed') THEN 1 END) as failed_count
                    FROM payments
                    WHERE DATE(created_at) = ?
                """, (today,))
                row = await cursor.fetchone()
                if row:
                    stats['today'] = {
                        'count': row[0] or 0,  # Только успешные платежи
                        'amount': row[1] or 0,  # Только сумма успешных платежей
                        'successful': row[0] or 0,
                        'pending': row[2] or 0,
                        'failed': row[3] or 0
                    }

                # Статистика за неделю - ТОЛЬКО успешные платежи
                week_ago = datetime.now() - timedelta(days=7)
                cursor = await db.execute("""
                    SELECT
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_count,
                        SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END) as successful_amount,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                        COUNT(CASE WHEN status IN ('cancelled', 'failed') THEN 1 END) as failed_count
                    FROM payments
                    WHERE created_at >= ?
                """, (week_ago,))
                row = await cursor.fetchone()
                if row:
                    stats['week'] = {
                        'count': row[0] or 0,  # Только успешные платежи
                        'amount': row[1] or 0,  # Только сумма успешных платежей
                        'successful': row[0] or 0,
                        'pending': row[2] or 0,
                        'failed': row[3] or 0
                    }

                # Общая статистика - ТОЛЬКО успешные платежи
                cursor = await db.execute("""
                    SELECT
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_count,
                        SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END) as successful_amount,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                        COUNT(CASE WHEN status IN ('cancelled', 'failed') THEN 1 END) as failed_count
                    FROM payments
                """)
                row = await cursor.fetchone()
                if row:
                    stats['total'] = {
                        'count': row[0] or 0,  # Только успешные платежи
                        'amount': row[1] or 0,  # Только сумма успешных платежей
                        'successful': row[0] or 0,
                        'pending': row[2] or 0,
                        'failed': row[3] or 0
                    }

            logger.info(f"📊 Статистика платежей получена:")
            logger.info(f"  - Сегодня: {stats['today']['successful']} успешных из {stats['today']['successful'] + stats['today']['pending'] + stats['today']['failed']} всего")
            logger.info(f"  - За неделю: {stats['week']['successful']} успешных из {stats['week']['successful'] + stats['week']['pending'] + stats['week']['failed']} всего")
            logger.info(f"  - Всего: {stats['total']['successful']} успешных из {stats['total']['successful'] + stats['total']['pending'] + stats['total']['failed']} всего")

            return stats

        except Exception as e:
            logger.error(f"Ошибка при получении статистики платежей: {e}")
            return {
                'today': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
                'week': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
                'month': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
                'total': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0}
            }


def create_payment_service(provider_token: str, currency: str = "RUB", 
                          provider_data: str = None, db: UniversalDatabase = None) -> YooKassaPaymentService:
    """Фабричная функция для создания сервиса платежей"""
    return YooKassaPaymentService(
        provider_token=provider_token,
        currency=currency,
        provider_data=provider_data,
        db=db
    )
