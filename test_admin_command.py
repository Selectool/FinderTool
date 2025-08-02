"""
Тестирование команды /admin
"""
import asyncio
import logging
from database.models import Database
from bot.handlers.admin import is_admin
from bot.utils.roles import TelegramUserPermissions

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_admin_command_access():
    """Тест доступа к команде /admin"""
    print("🔍 Тестирование доступа к команде /admin...")
    
    try:
        db = Database()
        await db.init_db()
        
        # Тестовые пользователи
        test_cases = [
            (5699315855, "developer", True),  # Разработчик
            (7610418399, "senior_admin", True),  # Старший админ
            (792247608, "admin", True),  # Администратор
            (123456789, "user", False),  # Обычный пользователь
        ]
        
        for user_id, expected_role, should_have_access in test_cases:
            # Проверяем доступ через новую функцию is_admin
            has_access = await is_admin(user_id, db)
            
            # Проверяем роль
            actual_role = TelegramUserPermissions.get_user_role(user_id)
            
            assert has_access == should_have_access, f"Неверный доступ для {user_id}: {has_access} != {should_have_access}"
            assert actual_role == expected_role, f"Неверная роль для {user_id}: {actual_role} != {expected_role}"
            
            status = "✅ ДОСТУП" if has_access else "❌ НЕТ ДОСТУПА"
            print(f"   {user_id}: роль={actual_role}, {status}")
        
        print("✅ Доступ к команде /admin: OK")
        return True
        
    except Exception as e:
        print(f"❌ Доступ к команде /admin: {e}")
        return False


async def test_admin_keyboard_import():
    """Тест импорта админской клавиатуры"""
    print("🔍 Тестирование импорта админской клавиатуры...")
    
    try:
        from bot.keyboards.inline import get_admin_keyboard
        
        # Создаем клавиатуру
        keyboard = get_admin_keyboard()
        assert keyboard is not None, "Админская inline клавиатура не создана"
        
        # Проверяем структуру
        keyboard_dict = keyboard.model_dump()
        assert 'inline_keyboard' in keyboard_dict, "Отсутствует inline_keyboard в структуре"
        
        buttons_count = 0
        for row in keyboard_dict['inline_keyboard']:
            buttons_count += len(row)
        
        assert buttons_count > 0, "Нет кнопок в админской клавиатуре"
        
        print("✅ Импорт админской клавиатуры: OK")
        print(f"   Найдено кнопок: {buttons_count}")
        return True
        
    except Exception as e:
        print(f"❌ Импорт админской клавиатуры: {e}")
        return False


async def test_database_connection():
    """Тест подключения к базе данных"""
    print("🔍 Тестирование подключения к базе данных...")
    
    try:
        db = Database()
        await db.init_db()
        
        # Проверяем получение пользователя
        user = await db.get_user(5699315855)
        assert user is not None, "Не удалось получить пользователя из БД"
        
        # Проверяем статистику
        stats = await db.get_stats()
        assert isinstance(stats, dict), "Статистика должна быть словарем"
        assert 'total_users' in stats, "Отсутствует total_users в статистике"
        
        print("✅ Подключение к базе данных: OK")
        print(f"   Всего пользователей: {stats['total_users']}")
        return True
        
    except Exception as e:
        print(f"❌ Подключение к базе данных: {e}")
        return False


async def test_role_system_integration():
    """Тест интеграции системы ролей"""
    print("🔍 Тестирование интеграции системы ролей...")
    
    try:
        # Проверяем основные функции системы ролей
        from bot.utils.roles import TelegramUserPermissions
        
        # Тест получения роли
        role = TelegramUserPermissions.get_user_role(5699315855)
        assert role == "developer", f"Неверная роль разработчика: {role}"
        
        # Тест проверки админского доступа
        has_access = TelegramUserPermissions.has_admin_access(5699315855, role)
        assert has_access, "Разработчик должен иметь админский доступ"
        
        # Тест обычного пользователя
        user_role = TelegramUserPermissions.get_user_role(123456789)
        assert user_role == "user", f"Неверная роль пользователя: {user_role}"
        
        user_access = TelegramUserPermissions.has_admin_access(123456789, user_role)
        assert not user_access, "Обычный пользователь не должен иметь админский доступ"
        
        print("✅ Интеграция системы ролей: OK")
        return True
        
    except Exception as e:
        print(f"❌ Интеграция системы ролей: {e}")
        return False


async def test_admin_handlers_structure():
    """Тест структуры админских обработчиков"""
    print("🔍 Тестирование структуры админских обработчиков...")
    
    try:
        from bot.handlers import admin
        
        # Проверяем наличие роутера
        assert hasattr(admin, 'router'), "Отсутствует router в админском модуле"
        
        # Проверяем наличие основных функций
        assert hasattr(admin, 'is_admin'), "Отсутствует функция is_admin"
        assert hasattr(admin, 'cmd_admin'), "Отсутствует обработчик cmd_admin"
        
        # Проверяем что is_admin - асинхронная функция
        import inspect
        assert inspect.iscoroutinefunction(admin.is_admin), "is_admin должна быть асинхронной функцией"
        
        print("✅ Структура админских обработчиков: OK")
        return True
        
    except Exception as e:
        print(f"❌ Структура админских обработчиков: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование команды /admin FinderTool")
    print("=" * 50)
    
    tests = [
        ("Подключение к БД", test_database_connection),
        ("Интеграция системы ролей", test_role_system_integration),
        ("Структура админских обработчиков", test_admin_handlers_structure),
        ("Импорт админской клавиатуры", test_admin_keyboard_import),
        ("Доступ к команде /admin", test_admin_command_access),
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
    print(f"📊 Результаты тестирования команды /admin:")
    print(f"Пройдено: {passed}/{total}")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Команда /admin готова к использованию.")
        print()
        print("✅ Теперь команда /admin должна работать для:")
        print("• 👨‍💻 developer (ID: 5699315855)")
        print("• 👑 senior_admin (ID: 7610418399)")
        print("• 🛡️ admin (ID: 792247608)")
        print()
        print("❌ И НЕ работать для:")
        print("• 👤 user (обычные пользователи)")
    else:
        print("⚠️ ЕСТЬ ПРОБЛЕМЫ! Необходимо исправить ошибки.")


if __name__ == "__main__":
    asyncio.run(main())
