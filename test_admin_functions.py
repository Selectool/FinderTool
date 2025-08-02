"""
Тестирование админ-функций Reply клавиатуры
"""
import asyncio
import logging
from database.models import Database
from bot.keyboards.reply import ReplyButtons, get_admin_menu_keyboard
from bot.utils.roles import TelegramUserPermissions

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_admin_keyboard():
    """Тест админской клавиатуры"""
    print("🔍 Тестирование админской Reply клавиатуры...")
    
    try:
        # Тест создания клавиатуры
        keyboard = get_admin_menu_keyboard()
        assert keyboard is not None, "Админская клавиатура не создана"
        
        # Проверяем наличие кнопок
        keyboard_dict = keyboard.model_dump()
        buttons_text = []
        
        for row in keyboard_dict.get('keyboard', []):
            for button in row:
                buttons_text.append(button.get('text', ''))
        
        expected_buttons = [
            ReplyButtons.STATISTICS,
            ReplyButtons.PAYMENTS,
            ReplyButtons.BROADCAST,
            ReplyButtons.USERS,
            ReplyButtons.MAIN_MENU
        ]
        
        for expected_button in expected_buttons:
            assert expected_button in buttons_text, f"Кнопка '{expected_button}' отсутствует в клавиатуре"
        
        print("✅ Админская клавиатура: OK")
        print(f"   Найдено кнопок: {len(buttons_text)}")
        print(f"   Кнопки: {', '.join(buttons_text)}")
        return True
        
    except Exception as e:
        print(f"❌ Админская клавиатура: {e}")
        return False


async def test_role_permissions():
    """Тест системы разрешений для админ-функций"""
    print("🔍 Тестирование разрешений админ-функций...")
    
    try:
        # Тестовые пользователи
        test_cases = [
            (5699315855, "developer", True),  # Разработчик
            (7610418399, "senior_admin", True),  # Старший админ
            (792247608, "admin", True),  # Администратор
            (123456789, "user", False),  # Обычный пользователь
        ]
        
        for user_id, expected_role, should_have_access in test_cases:
            # Проверяем роль
            actual_role = TelegramUserPermissions.get_user_role(user_id)
            assert actual_role == expected_role, f"Неверная роль для {user_id}: {actual_role} != {expected_role}"
            
            # Проверяем доступ к админ-панели
            has_access = TelegramUserPermissions.has_admin_access(user_id, actual_role)
            assert has_access == should_have_access, f"Неверные права доступа для {user_id}: {has_access} != {should_have_access}"
            
            print(f"   ✅ {user_id}: роль={actual_role}, доступ={has_access}")
        
        print("✅ Система разрешений: OK")
        return True
        
    except Exception as e:
        print(f"❌ Система разрешений: {e}")
        return False


async def test_database_stats():
    """Тест получения статистики из базы данных"""
    print("🔍 Тестирование получения статистики...")
    
    try:
        db = Database()
        await db.init_db()
        
        # Получаем статистику
        stats = await db.get_stats()
        
        # Проверяем обязательные поля
        required_fields = ['total_users', 'active_subscribers', 'requests_today']
        for field in required_fields:
            assert field in stats, f"Отсутствует поле '{field}' в статистике"
            assert isinstance(stats[field], int), f"Поле '{field}' должно быть числом"
        
        print("✅ Статистика базы данных: OK")
        print(f"   Всего пользователей: {stats['total_users']}")
        print(f"   Активных подписчиков: {stats['active_subscribers']}")
        print(f"   Запросов сегодня: {stats['requests_today']}")
        return True
        
    except Exception as e:
        print(f"❌ Статистика базы данных: {e}")
        return False


async def test_payment_service():
    """Тест сервиса платежей для админ-статистики"""
    print("🔍 Тестирование сервиса платежей...")
    
    try:
        from services.payment_service import create_payment_service
        from config import YOOKASSA_PROVIDER_TOKEN, YOOKASSA_CURRENCY, YOOKASSA_PROVIDER_DATA
        from database.models import Database
        
        db = Database()
        await db.init_db()
        
        # Создаем сервис платежей
        payment_service = create_payment_service(
            provider_token=YOOKASSA_PROVIDER_TOKEN,
            currency=YOOKASSA_CURRENCY,
            provider_data=YOOKASSA_PROVIDER_DATA,
            db=db
        )
        
        # Проверяем режим
        mode = "LIVE" if not payment_service.is_test_mode else "TEST"
        print(f"   Режим ЮKassa: {mode}")
        
        # Получаем статистику платежей
        stats = await payment_service.get_payment_statistics()
        
        if stats:
            # Проверяем структуру статистики
            required_periods = ['today', 'week', 'total']
            for period in required_periods:
                assert period in stats, f"Отсутствует период '{period}' в статистике платежей"
                
                period_stats = stats[period]
                required_fields = ['count', 'successful', 'amount']
                for field in required_fields:
                    assert field in period_stats, f"Отсутствует поле '{field}' в статистике за {period}"
            
            print("✅ Сервис платежей: OK")
            print(f"   Всего платежей: {stats['total']['count']}")
            print(f"   Успешных: {stats['total']['successful']}")
            print(f"   Общая сумма: {stats['total']['amount'] // 100} ₽")
        else:
            print("⚠️ Сервис платежей: статистика пуста (это нормально для нового бота)")
        
        return True
        
    except Exception as e:
        print(f"❌ Сервис платежей: {e}")
        return False


async def test_reply_buttons_constants():
    """Тест констант Reply кнопок"""
    print("🔍 Тестирование констант Reply кнопок...")
    
    try:
        from bot.keyboards.reply import ReplyButtons, is_reply_button
        
        # Проверяем админские кнопки
        admin_buttons = [
            ReplyButtons.STATISTICS,
            ReplyButtons.PAYMENTS,
            ReplyButtons.BROADCAST,
            ReplyButtons.USERS,
            ReplyButtons.ADMIN_PANEL
        ]
        
        for button in admin_buttons:
            assert isinstance(button, str), f"Кнопка {button} должна быть строкой"
            assert len(button) > 0, f"Кнопка {button} не должна быть пустой"
            assert is_reply_button(button), f"Кнопка {button} не распознается как Reply кнопка"
        
        print("✅ Константы Reply кнопок: OK")
        print(f"   Проверено админских кнопок: {len(admin_buttons)}")
        return True
        
    except Exception as e:
        print(f"❌ Константы Reply кнопок: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование админ-функций FinderTool")
    print("=" * 50)
    
    tests = [
        ("Константы Reply кнопок", test_reply_buttons_constants),
        ("Админская клавиатура", test_admin_keyboard),
        ("Система разрешений", test_role_permissions),
        ("Статистика БД", test_database_stats),
        ("Сервис платежей", test_payment_service),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
            print()
        except Exception as e:
            print(f"❌ {test_name}: КРИТИЧЕСКАЯ ОШИБКА - {e}")
            print()
    
    print("=" * 50)
    print(f"📊 Результаты тестирования админ-функций:")
    print(f"Пройдено: {passed}/{total}")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Админ-функции готовы к использованию.")
        print()
        print("✅ Теперь в Telegram боте должны работать:")
        print("• 📊 Статистика - показ статистики бота")
        print("• 💳 Платежи - статистика платежей ЮKassa")
        print("• 📢 Рассылка - информация о рассылках")
        print("• 👥 Пользователи - управление пользователями")
    else:
        print("⚠️ ЕСТЬ ПРОБЛЕМЫ! Необходимо исправить ошибки.")


if __name__ == "__main__":
    asyncio.run(main())
