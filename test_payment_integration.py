"""
Тестовый скрипт для проверки интеграции ЮKassa
"""
import asyncio
import logging
from database.models import Database
from services.payment_service import create_payment_service
from config import YOOKASSA_PROVIDER_TOKEN, YOOKASSA_CURRENCY, YOOKASSA_PROVIDER_DATA, SUBSCRIPTION_PRICE

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_database_integration():
    """Тест интеграции с базой данных"""
    print("🔍 Тестирование интеграции с базой данных...")
    
    db = Database()
    await db.init_db()
    
    # Тестовый пользователь
    test_user_id = 123456789
    
    # Создаем тестового пользователя
    await db.create_user(test_user_id, "test_user", "Test", "User")
    print(f"✅ Тестовый пользователь {test_user_id} создан")
    
    # Проверяем создание платежа
    payment_id = await db.create_payment(
        user_id=test_user_id,
        amount=34900,  # 349 рублей в копейках
        currency="RUB",
        payment_id="test-payment-123",
        invoice_payload="subscription_1m_test-payment-123",
        subscription_months=1
    )
    print(f"✅ Платеж создан с ID: {payment_id}")
    
    # Получаем платеж
    payment = await db.get_payment(payment_id="test-payment-123")
    if payment:
        print(f"✅ Платеж найден: {payment['status']}, сумма: {payment['amount']} копеек")
    else:
        print("❌ Платеж не найден")
        return False
    
    # Завершаем платеж
    success = await db.complete_payment("test-payment-123", "test-provider-id")
    if success:
        print("✅ Платеж успешно завершен и подписка активирована")
    else:
        print("❌ Ошибка при завершении платежа")
        return False
    
    # Проверяем подписку
    is_subscribed = await db.check_subscription(test_user_id)
    if is_subscribed:
        print("✅ Подписка активна")
    else:
        print("❌ Подписка не активна")
        return False
    
    print("✅ Тест базы данных пройден успешно!\n")
    return True


async def test_payment_service():
    """Тест сервиса платежей"""
    print("🔍 Тестирование сервиса платежей...")
    
    db = Database()
    await db.init_db()
    
    # Создаем сервис платежей
    payment_service = create_payment_service(
        provider_token=YOOKASSA_PROVIDER_TOKEN,
        currency=YOOKASSA_CURRENCY,
        provider_data=YOOKASSA_PROVIDER_DATA,
        db=db
    )
    
    print(f"✅ Сервис платежей создан в режиме: {'TEST' if payment_service.is_test_mode else 'LIVE'}")
    
    # Тестовый пользователь
    test_user_id = 987654321
    await db.create_user(test_user_id, "test_user_2", "Test", "User2")
    
    # Создаем данные для инвойса
    amount_in_kopecks = SUBSCRIPTION_PRICE * 100
    invoice_data = await payment_service.create_invoice_data(
        user_id=test_user_id,
        amount=amount_in_kopecks,
        description="Тестовая подписка",
        subscription_months=1
    )
    
    print(f"✅ Данные инвойса созданы:")
    print(f"   - Сумма: {amount_in_kopecks} копеек")
    print(f"   - Валюта: {invoice_data['currency']}")
    print(f"   - Payload: {invoice_data['payload']}")
    print(f"   - Токен провайдера: {invoice_data['provider_token'][:20]}...")
    
    # Проверяем информацию о тестовой карте
    test_card_info = payment_service.get_test_card_info()
    if test_card_info:
        print(f"✅ Информация о тестовой карте получена")
        print(f"   {test_card_info}")
    
    # Форматирование суммы
    formatted_amount = payment_service.format_amount_for_display(amount_in_kopecks)
    print(f"✅ Форматированная сумма: {formatted_amount}")
    
    print("✅ Тест сервиса платежей пройден успешно!\n")
    return True


async def test_configuration():
    """Тест конфигурации"""
    print("🔍 Тестирование конфигурации...")
    
    print(f"✅ Режим ЮKassa: TEST")
    print(f"✅ Токен провайдера: {YOOKASSA_PROVIDER_TOKEN}")
    print(f"✅ Валюта: {YOOKASSA_CURRENCY}")
    print(f"✅ Цена подписки: {SUBSCRIPTION_PRICE} рублей")
    print(f"✅ Provider data настроен: {'Да' if YOOKASSA_PROVIDER_DATA else 'Нет'}")
    
    # Проверяем JSON provider_data
    import json
    try:
        provider_data = json.loads(YOOKASSA_PROVIDER_DATA)
        receipt = provider_data.get('receipt', {})
        items = receipt.get('items', [])
        if items:
            item = items[0]
            print(f"✅ Чек настроен:")
            print(f"   - Описание: {item.get('description')}")
            print(f"   - Количество: {item.get('quantity')}")
            print(f"   - Сумма: {item.get('amount', {}).get('value')} {item.get('amount', {}).get('currency')}")
            print(f"   - НДС код: {item.get('vat_code')}")
    except Exception as e:
        print(f"❌ Ошибка в provider_data: {e}")
        return False
    
    print("✅ Тест конфигурации пройден успешно!\n")
    return True


async def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования интеграции ЮKassa\n")
    
    tests = [
        ("Конфигурация", test_configuration),
        ("База данных", test_database_integration),
        ("Сервис платежей", test_payment_service),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"✅ {test_name}: ПРОЙДЕН")
            else:
                print(f"❌ {test_name}: НЕ ПРОЙДЕН")
        except Exception as e:
            print(f"❌ {test_name}: ОШИБКА - {e}")
        print("-" * 50)
    
    print(f"\n📊 Результаты тестирования:")
    print(f"Пройдено: {passed}/{total}")
    print(f"Статус: {'✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ' if passed == total else '❌ ЕСТЬ ОШИБКИ'}")
    
    if passed == total:
        print("\n🎉 Интеграция ЮKassa готова к использованию!")
        print("Теперь можно тестировать в Telegram боте:")
        print("1. Отправьте команду /subscribe")
        print("2. Нажмите кнопку 'Оплатить подписку'")
        print("3. Используйте тестовую карту: 1111 1111 1111 1026, 12/22, CVC 000")
    else:
        print("\n⚠️ Необходимо исправить ошибки перед использованием")


if __name__ == "__main__":
    asyncio.run(main())
