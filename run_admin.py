#!/usr/bin/env python3
"""
Скрипт для запуска админ-панели с автоматическим определением окружения
"""
import uvicorn
import sys
import os
from admin.config import HOST, PORT, DEBUG, LOG_LEVEL, ENVIRONMENT

def print_startup_info():
    """Вывод информации о запуске"""
    print("=" * 60)
    print("🚀 TELEGRAM CHANNEL FINDER BOT - АДМИН-ПАНЕЛЬ")
    print("=" * 60)
    print(f"🌍 Окружение: {ENVIRONMENT.upper()}")
    print(f"🏠 Адрес: http://{HOST}:{PORT}")
    print(f"📊 Debug режим: {'включен' if DEBUG else 'выключен'}")
    print(f"📝 Уровень логов: {LOG_LEVEL}")

    if ENVIRONMENT == "development":
        print("🔧 РЕЖИМ РАЗРАБОТКИ")
        print("  • Автоматическая перезагрузка включена")
        print("  • Расширенное логирование")
        print("  • Тестовые платежи ЮKassa")
        print("  • Доступ только с localhost")
    else:
        print("🏭 ПРОДАКШН РЕЖИМ")
        print("  • Реальные платежи ЮKassa")
        print("  • Оптимизированное логирование")
        print("  • Проверки безопасности активны")

    print(f"👤 Админ по умолчанию: admin / admin123")
    print("⚠️  ОБЯЗАТЕЛЬНО смените пароль после первого входа!")
    print("=" * 60)

def check_environment():
    """Проверка окружения перед запуском"""
    if ENVIRONMENT == "production":
        # Дополнительные проверки для продакшн
        required_env_vars = [
            "ADMIN_SECRET_KEY",
            "JWT_SECRET_KEY",
            "YOOKASSA_SHOP_ID",
            "YOOKASSA_SECRET_KEY"
        ]

        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var) or os.getenv(var) in [
                "your-super-secret-admin-key-change-in-production",
                "your-jwt-secret-key-change-in-production"
            ]:
                missing_vars.append(var)

        if missing_vars:
            print("❌ ОШИБКА: Не настроены обязательные переменные для продакшн:")
            for var in missing_vars:
                print(f"  • {var}")
            print("\nИсправьте конфигурацию перед запуском в продакшн режиме!")
            sys.exit(1)

if __name__ == "__main__":
    try:
        check_environment()
        print_startup_info()

        uvicorn.run(
            "admin.app:app",
            host=HOST,
            port=PORT,
            reload=DEBUG,
            log_level=LOG_LEVEL.lower(),
            access_log=DEBUG  # Подробные логи доступа только в debug режиме
        )
    except KeyboardInterrupt:
        print("\n👋 Админ-панель остановлена пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска админ-панели: {e}")
        sys.exit(1)
