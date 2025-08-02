#!/usr/bin/env python3
"""
Тестирование системы оплаты ЮKassa
Production-ready тестирование всех компонентов платежной системы
"""
import asyncio
import logging
import json
from datetime import datetime

from database.models import Database
from services.payment_service import create_payment_service
from config import (
    YOOKASSA_PROVIDER_TOKEN, YOOKASSA_CURRENCY, YOOKASSA_PROVIDER_DATA,
    SUBSCRIPTION_PRICE, YOOKASSA_MODE
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_payment_service_initialization():
    """Тест инициализации сервиса платежей"""
    print("\n" + "="*60)
    print("🔧 ТЕСТ: Инициализация сервиса платежей")
    print("="*60)
    
    try:
        db = Database()
        await db.init_db()
        
        payment_service = create_payment_service(
            provider_token=YOOKASSA_PROVIDER_TOKEN,
            currency=YOOKASSA_CURRENCY,
            provider_data=YOOKASSA_PROVIDER_DATA,
            db=db
        )
        
        print(f"✅ Сервис платежей инициализирован")
        print(f"   - Режим: {YOOKASSA_MODE}")
        print(f"   - Тестовый режим: {payment_service.is_test_mode}")
        print(f"   - Валюта: {payment_service.currency}")
        print(f"   - Токен: {payment_service.provider_token[:20]}...{payment_service.provider_token[-10:]}")
        
        return payment_service, db
        
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        return None, None


async def test_invoice_creation(payment_service, db):
    """Тест создания инвойса"""
    print("\n" + "="*60)
    print("📄 ТЕСТ: Создание инвойса")
    print("="*60)
    
    try:
        test_user_id = 123456789
        amount = SUBSCRIPTION_PRICE * 100  # В копейках
        
        # Создаем тестового пользователя
        await db.create_user(test_user_id, "test_user", "Test", "User")
        print(f"✅ Тестовый пользователь {test_user_id} создан")
        
        # Создаем инвойс
        invoice_data = await payment_service.create_invoice_data(
            user_id=test_user_id,
            amount=amount,
            description=f"Подписка Channel Finder Bot - {SUBSCRIPTION_PRICE}₽/месяц",
            subscription_months=1
        )
        
        print(f"✅ Инвойс создан успешно")
        print(f"   - Название: {invoice_data['title']}")
        print(f"   - Описание: {invoice_data['description']}")
        print(f"   - Сумма: {invoice_data['prices'][0].amount} копеек ({invoice_data['prices'][0].amount/100:.2f} ₽)")
        print(f"   - Валюта: {invoice_data['currency']}")
        print(f"   - Payload: {invoice_data['payload']}")
        
        # Проверяем provider_data
        if invoice_data['provider_data']:
            provider_data = json.loads(invoice_data['provider_data'])
            print(f"   - Provider data: {json.dumps(provider_data, ensure_ascii=False, indent=4)}")
        
        return invoice_data
        
    except Exception as e:
        print(f"❌ Ошибка создания инвойса: {e}")
        return None


async def test_database_operations(db):
    """Тест операций с базой данных"""
    print("\n" + "="*60)
    print("🗄️ ТЕСТ: Операции с базой данных")
    print("="*60)
    
    try:
        # Тестируем создание платежа
        test_payment_id = "test-payment-12345"
        test_user_id = 123456789
        
        await db.create_payment(
            user_id=test_user_id,
            amount=34900,
            currency="RUB",
            payment_id=test_payment_id,
            invoice_payload=f"subscription_1m_{test_payment_id}",
            subscription_months=1
        )
        print(f"✅ Платеж создан в базе данных")
        
        # Получаем платеж
        payment = await db.get_payment(payment_id=test_payment_id)
        if payment:
            print(f"✅ Платеж найден в базе данных")
            print(f"   - ID: {payment['payment_id']}")
            print(f"   - Пользователь: {payment['user_id']}")
            print(f"   - Сумма: {payment['amount']} копеек")
            print(f"   - Статус: {payment['status']}")
        else:
            print(f"❌ Платеж не найден в базе данных")
        
        # Тестируем завершение платежа
        success = await db.complete_payment(
            payment_id=test_payment_id,
            provider_payment_id="yookassa-test-12345"
        )
        
        if success:
            print(f"✅ Платеж успешно завершен")
            
            # Проверяем активацию подписки
            is_subscribed = await db.check_subscription(test_user_id)
            if is_subscribed:
                print(f"✅ Подписка пользователя активирована")
            else:
                print(f"❌ Подписка пользователя не активирована")
        else:
            print(f"❌ Не удалось завершить платеж")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка операций с базой данных: {e}")
        return False


async def test_configuration():
    """Тест конфигурации системы"""
    print("\n" + "="*60)
    print("⚙️ ТЕСТ: Конфигурация системы")
    print("="*60)
    
    try:
        print(f"✅ Конфигурация загружена")
        print(f"   - Режим ЮKassa: {YOOKASSA_MODE}")
        print(f"   - Цена подписки: {SUBSCRIPTION_PRICE} ₽")
        print(f"   - Валюта: {YOOKASSA_CURRENCY}")
        print(f"   - Токен установлен: {'Да' if YOOKASSA_PROVIDER_TOKEN else 'Нет'}")
        print(f"   - Provider data установлен: {'Да' if YOOKASSA_PROVIDER_DATA else 'Нет'}")
        
        # Проверяем provider_data
        if YOOKASSA_PROVIDER_DATA:
            provider_data = json.loads(YOOKASSA_PROVIDER_DATA)
            print(f"   - Provider data валиден: Да")
            print(f"   - Товар в чеке: {provider_data['receipt']['items'][0]['description']}")
            print(f"   - Сумма в чеке: {provider_data['receipt']['items'][0]['amount']['value']} {provider_data['receipt']['items'][0]['amount']['currency']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка конфигурации: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🚀 ЗАПУСК ТЕСТИРОВАНИЯ СИСТЕМЫ ОПЛАТЫ")
    print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Тест конфигурации
    config_ok = await test_configuration()
    
    # Тест инициализации
    payment_service, db = await test_payment_service_initialization()
    
    if not payment_service or not db:
        print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось инициализировать систему")
        return
    
    # Тест создания инвойса
    invoice_data = await test_invoice_creation(payment_service, db)
    
    # Тест операций с базой данных
    db_ok = await test_database_operations(db)
    
    # Итоговый отчет
    print("\n" + "="*60)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("="*60)
    
    tests = [
        ("Конфигурация", config_ok),
        ("Инициализация сервиса", payment_service is not None),
        ("Создание инвойса", invoice_data is not None),
        ("Операции с БД", db_ok)
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for test_name, result in tests:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name:.<30} {status}")
    
    print(f"\nРезультат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система готова к работе.")
    else:
        print("⚠️ ЕСТЬ ПРОБЛЕМЫ! Требуется исправление.")


if __name__ == "__main__":
    asyncio.run(main())
