"""
Финальная проверка готовности системы к продакшн
"""
import asyncio
import logging
from database.models import Database
from services.payment_service import create_payment_service
from config import *

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_clean_database():
    """Проверить, что база данных очищена от тестовых данных"""
    print("🔍 Проверка чистоты базы данных...")
    
    try:
        db = Database()
        await db.init_db()
        
        import aiosqlite
        async with aiosqlite.connect(db.db_path) as conn:
            # Проверяем платежи
            cursor = await conn.execute("SELECT COUNT(*) FROM payments")
            payments_count = (await cursor.fetchone())[0]
            
            # Проверяем запросы
            cursor = await conn.execute("SELECT COUNT(*) FROM requests")
            requests_count = (await cursor.fetchone())[0]
            
            # Проверяем пользователей
            cursor = await conn.execute("SELECT COUNT(*) FROM users")
            users_count = (await cursor.fetchone())[0]
            
            print(f"   💳 Платежей: {payments_count}")
            print(f"   📝 Запросов: {requests_count}")
            print(f"   👥 Пользователей: {users_count}")
            
            # Проверяем, что остались только админы
            if users_count <= 3 and payments_count == 0:
                print("   ✅ База данных очищена от тестовых данных")
                return True
            else:
                print("   ⚠️ В базе данных могут остаться тестовые данные")
                return False
                
    except Exception as e:
        print(f"   ❌ Ошибка проверки БД: {e}")
        return False


async def check_payment_system_live():
    """Проверить, что платежная система в LIVE режиме"""
    print("\n🔍 Проверка режима платежной системы...")
    
    try:
        print(f"   Режим ЮKassa: {YOOKASSA_MODE}")
        print(f"   Токен провайдера: {YOOKASSA_PROVIDER_TOKEN[:20]}...")
        
        if YOOKASSA_MODE != "LIVE":
            print("   ❌ ЮKassa НЕ в LIVE режиме!")
            return False
        
        if ":TEST:" in YOOKASSA_PROVIDER_TOKEN:
            print("   ❌ Используется тестовый токен!")
            return False
        
        # Проверяем сервис
        db = Database()
        await db.init_db()
        
        payment_service = create_payment_service(
            provider_token=YOOKASSA_PROVIDER_TOKEN,
            currency=YOOKASSA_CURRENCY,
            provider_data=YOOKASSA_PROVIDER_DATA,
            db=db
        )
        
        if payment_service.is_test_mode:
            print("   ❌ Сервис платежей в тестовом режиме!")
            return False
        
        print("   ✅ Платежная система в LIVE режиме")
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка проверки платежей: {e}")
        return False


async def check_admin_access():
    """Проверить доступ админов"""
    print("\n🔍 Проверка доступа админов...")
    
    try:
        from bot.utils.roles import TelegramUserPermissions
        
        admins = [
            (5699315855, "developer"),
            (7610418399, "senior_admin"),
            (792247608, "admin")
        ]
        
        for user_id, expected_role in admins:
            role = TelegramUserPermissions.get_user_role(user_id)
            has_access = TelegramUserPermissions.has_admin_access(user_id, role)
            
            if role == expected_role and has_access:
                print(f"   ✅ {user_id}: {role}")
            else:
                print(f"   ❌ {user_id}: проблема с ролью {role}")
                return False
        
        print("   ✅ Все админы имеют корректный доступ")
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка проверки админов: {e}")
        return False


async def check_telethon_session():
    """Проверить Telethon сессию"""
    print("\n🔍 Проверка Telethon сессии...")

    try:
        if not SESSION_STRING:
            print("   ❌ SESSION_STRING не установлена")
            return False

        from services.channel_finder import ChannelFinder

        finder = ChannelFinder(
            API_ID,
            API_HASH,
            session_string=SESSION_STRING
        )

        # Инициализируем клиент
        await finder.init_client()

        if await finder.client.is_user_authorized():
            print("   ✅ Telethon сессия авторизована")
            await finder.close_client()
            return True
        else:
            print("   ❌ Telethon сессия не авторизована")
            await finder.close_client()
            return False

    except Exception as e:
        print(f"   ❌ Ошибка Telethon: {e}")
        return False


def check_environment_config():
    """Проверить конфигурацию окружения"""
    print("\n🔍 Проверка конфигурации окружения...")
    
    try:
        # Проверяем основные переменные
        required_vars = {
            'BOT_TOKEN': BOT_TOKEN,
            'API_ID': API_ID,
            'API_HASH': API_HASH,
            'YOOKASSA_LIVE_TOKEN': YOOKASSA_LIVE_TOKEN,
            'SESSION_STRING': SESSION_STRING
        }
        
        missing = []
        for var_name, var_value in required_vars.items():
            if not var_value or (isinstance(var_value, int) and var_value == 0):
                missing.append(var_name)
        
        if missing:
            print(f"   ❌ Отсутствуют переменные: {', '.join(missing)}")
            return False
        
        # Проверяем цены и лимиты
        print(f"   💰 Цена подписки: {SUBSCRIPTION_PRICE}₽")
        print(f"   🆓 Бесплатных запросов: {FREE_REQUESTS_LIMIT}")
        
        if SUBSCRIPTION_PRICE <= 0:
            print("   ❌ Некорректная цена подписки")
            return False
        
        if FREE_REQUESTS_LIMIT <= 0:
            print("   ❌ Некорректный лимит бесплатных запросов")
            return False
        
        print("   ✅ Конфигурация окружения корректна")
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка конфигурации: {e}")
        return False


async def main():
    """Основная функция проверки"""
    print("🚀 Финальная проверка готовности к продакшн")
    print("=" * 60)
    
    checks = [
        ("Чистота базы данных", check_clean_database),
        ("Режим платежной системы", check_payment_system_live),
        ("Доступ админов", check_admin_access),
        ("Telethon сессия", check_telethon_session),
        ("Конфигурация окружения", check_environment_config)
    ]
    
    passed = 0
    total = len(checks)
    
    for check_name, check_func in checks:
        try:
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()
            
            if result:
                passed += 1
        except Exception as e:
            print(f"\n❌ Критическая ошибка в '{check_name}': {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 РЕЗУЛЬТАТ: {passed}/{total} проверок пройдено")
    
    if passed == total:
        print("🎉 СИСТЕМА ГОТОВА К ПРОДАКШН!")
        print("\n✅ Все проверки пройдены успешно")
        print("✅ Тестовые данные очищены")
        print("✅ Платежная система в LIVE режиме")
        print("✅ Админы настроены корректно")
        print("✅ Telethon сессия работает")
        print("✅ Конфигурация корректна")
        
        print("\n🚀 МОЖНО ЗАПУСКАТЬ В ПРОДАКШН!")
        print("\n💡 Следующие шаги:")
        print("1. Убедитесь, что бот запущен")
        print("2. Протестируйте основные функции")
        print("3. Проведите тестовую оплату")
        print("4. Мониторьте логи на ошибки")
        print("5. Настройте мониторинг и алерты")
        
    else:
        print("❌ СИСТЕМА НЕ ГОТОВА К ПРОДАКШН!")
        print(f"\nНе пройдено проверок: {total - passed}")
        print("Исправьте ошибки перед запуском в продакшн")
        
        if passed < total // 2:
            print("\n⚠️ КРИТИЧНО: Много проблем!")
            print("Рекомендуется полная проверка конфигурации")


if __name__ == "__main__":
    asyncio.run(main())
