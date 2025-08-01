#!/usr/bin/env python3
"""
Скрипт для настройки окружения разработки/продакшн
"""
import os
import sys
import shutil
import argparse
from pathlib import Path

def setup_development():
    """Настройка окружения разработки"""
    print("🔧 Настройка окружения разработки...")
    
    # Копируем .env.development в .env если он не существует
    if not os.path.exists(".env"):
        if os.path.exists(".env.development"):
            shutil.copy(".env.development", ".env")
            print("✅ Скопирован .env.development -> .env")
        else:
            print("❌ Файл .env.development не найден!")
            return False
    else:
        print("ℹ️  Файл .env уже существует")
    
    # Устанавливаем переменную окружения
    with open(".env", "r", encoding="utf-8") as f:
        content = f.read()
    
    if "ENVIRONMENT=development" not in content:
        # Добавляем или обновляем ENVIRONMENT
        lines = content.split("\n")
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("ENVIRONMENT="):
                lines[i] = "ENVIRONMENT=development"
                updated = True
                break
        
        if not updated:
            lines.insert(0, "ENVIRONMENT=development")
        
        with open(".env", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    
    print("✅ Окружение разработки настроено")
    print("🏠 Админ-панель будет доступна на: http://127.0.0.1:8080")
    print("💳 Платежи: ТЕСТОВЫЙ режим ЮKassa")
    return True

def setup_production():
    """Настройка продакшн окружения"""
    print("🏭 Настройка продакшн окружения...")
    
    # Проверяем наличие .env.example
    if not os.path.exists(".env.example"):
        print("❌ Файл .env.example не найден!")
        return False
    
    # Копируем .env.example в .env если он не существует
    if not os.path.exists(".env"):
        shutil.copy(".env.example", ".env")
        print("✅ Скопирован .env.example -> .env")
    else:
        print("ℹ️  Файл .env уже существует")
    
    # Устанавливаем переменную окружения
    with open(".env", "r", encoding="utf-8") as f:
        content = f.read()
    
    if "ENVIRONMENT=production" not in content:
        # Добавляем или обновляем ENVIRONMENT
        lines = content.split("\n")
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("ENVIRONMENT="):
                lines[i] = "ENVIRONMENT=production"
                updated = True
                break
        
        if not updated:
            lines.insert(0, "ENVIRONMENT=production")
        
        with open(".env", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    
    print("✅ Продакшн окружение настроено")
    print("⚠️  ВНИМАНИЕ: Обязательно настройте следующие переменные в .env:")
    print("  • BOT_TOKEN")
    print("  • API_ID и API_HASH")
    print("  • ADMIN_USER_ID")
    print("  • ADMIN_SECRET_KEY")
    print("  • JWT_SECRET_KEY")
    print("  • YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY")
    print("  • ADMIN_ALLOWED_HOSTS и ADMIN_CORS_ORIGINS")
    return True

def show_current_environment():
    """Показать текущее окружение"""
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            content = f.read()
        
        env = "development"  # по умолчанию
        for line in content.split("\n"):
            if line.startswith("ENVIRONMENT="):
                env = line.split("=", 1)[1].strip()
                break
        
        print(f"🌍 Текущее окружение: {env.upper()}")
        
        if env == "development":
            print("🔧 Режим разработки:")
            print("  • Хост: 127.0.0.1:8080")
            print("  • Debug: включен")
            print("  • ЮKassa: TEST режим")
            print("  • База данных: bot_dev.db")
        else:
            print("🏭 Продакшн режим:")
            print("  • Хост: 0.0.0.0:8080")
            print("  • Debug: выключен")
            print("  • ЮKassa: LIVE режим")
            print("  • База данных: bot.db")
    else:
        print("❌ Файл .env не найден")

def validate_environment():
    """Валидация текущего окружения"""
    print("🔍 Проверка конфигурации...")
    
    try:
        # Импортируем валидатор
        sys.path.append(os.getcwd())
        from admin.utils.config_validator import ConfigValidator
        from admin.config import ENVIRONMENT
        
        # Собираем конфигурацию
        config_dict = {}
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config_dict[key] = value
        
        # Валидация
        validator = ConfigValidator(ENVIRONMENT)
        is_valid = validator.validate_all(config_dict)
        
        print(validator.get_report())
        
        if is_valid:
            print("✅ Конфигурация корректна")
        else:
            print("❌ Обнаружены ошибки в конфигурации")
            
        return is_valid
        
    except ImportError as e:
        print(f"❌ Ошибка импорта валидатора: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка валидации: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Управление окружениями Telegram Channel Finder Bot")
    parser.add_argument("command", choices=["dev", "prod", "status", "validate"], 
                       help="Команда: dev (разработка), prod (продакшн), status (текущее состояние), validate (проверка)")
    
    args = parser.parse_args()
    
    print("🤖 Telegram Channel Finder Bot - Управление окружениями")
    print("=" * 60)
    
    if args.command == "dev":
        success = setup_development()
        if success:
            print("\n🚀 Для запуска админ-панели выполните:")
            print("   python run_admin.py")
    
    elif args.command == "prod":
        success = setup_production()
        if success:
            print("\n🚀 После настройки .env выполните:")
            print("   python run_admin.py")
    
    elif args.command == "status":
        show_current_environment()
    
    elif args.command == "validate":
        validate_environment()

if __name__ == "__main__":
    main()
