#!/usr/bin/env python3
"""
Тестовый скрипт для проверки всех вариантов запуска
Проверяет доступность файлов и корректность импортов
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

def test_environment():
    """Тест переменных окружения"""
    print("🔍 Проверка переменных окружения...")
    
    required_vars = ['BOT_TOKEN', 'DATABASE_URL', 'ADMIN_HOST', 'ADMIN_PORT']
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {'*' * 10}...{value[-4:] if len(value) > 4 else value}")
        else:
            print(f"  ❌ {var}: Не установлен")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️ Отсутствуют переменные: {', '.join(missing_vars)}")
        return False
    
    print("✅ Все переменные окружения установлены")
    return True

def test_files():
    """Тест наличия файлов"""
    print("\n📁 Проверка файлов...")
    
    files_to_check = [
        'app.py',
        'main.py', 
        'run_admin.py',
        'dokploy_launcher.py',
        'start_production.py'
    ]
    
    available_files = []
    
    for file in files_to_check:
        if os.path.exists(file):
            print(f"  ✅ {file}: Найден")
            available_files.append(file)
        else:
            print(f"  ❌ {file}: Не найден")
    
    return available_files

def test_imports():
    """Тест импортов"""
    print("\n📦 Проверка импортов...")
    
    imports_to_test = [
        ('aiogram', 'Telegram Bot API'),
        ('fastapi', 'FastAPI Framework'),
        ('uvicorn', 'ASGI Server'),
        ('asyncpg', 'PostgreSQL Driver'),
        ('jwt', 'JWT Tokens'),
        ('aiosqlite', 'SQLite Driver')
    ]
    
    available_imports = []
    
    for module, description in imports_to_test:
        try:
            __import__(module)
            print(f"  ✅ {module}: {description}")
            available_imports.append(module)
        except ImportError:
            print(f"  ❌ {module}: {description} - Не установлен")
    
    return available_imports

def test_launch_options():
    """Тест вариантов запуска"""
    print("\n🚀 Доступные варианты запуска:")
    
    launch_options = []
    
    # Вариант 1: Единое приложение
    if os.path.exists('app.py'):
        try:
            import app
            print("  ✅ python app.py - Единое приложение (РЕКОМЕНДУЕТСЯ)")
            launch_options.append('app.py')
        except Exception as e:
            print(f"  ⚠️ python app.py - Ошибка импорта: {e}")
    
    # Вариант 2: Dokploy launcher
    if os.path.exists('dokploy_launcher.py'):
        print("  ✅ python dokploy_launcher.py - Dokploy launcher")
        launch_options.append('dokploy_launcher.py')
    
    # Вариант 3: Раздельные процессы
    if os.path.exists('main.py') and os.path.exists('run_admin.py'):
        print("  ✅ python start_production.py - Раздельные процессы")
        launch_options.append('start_production.py')
    
    # Вариант 4: Только бот
    if os.path.exists('main.py'):
        print("  ✅ python main.py - Только Telegram бот")
        launch_options.append('main.py')
    
    # Вариант 5: Только админ-панель
    if os.path.exists('run_admin.py'):
        print("  ✅ python run_admin.py - Только админ-панель")
        launch_options.append('run_admin.py')
    
    return launch_options

def recommend_launch_command():
    """Рекомендация команды запуска"""
    print("\n🎯 Рекомендация для Dokploy Run Command:")
    
    if os.path.exists('app.py'):
        print("  🥇 ЛУЧШИЙ ВЫБОР: python app.py")
        print("     • Единый процесс для бота + админ-панели")
        print("     • Оптимальное использование ресурсов")
        print("     • Production-ready архитектура")
        print("     • Health checks и мониторинг")
    elif os.path.exists('dokploy_launcher.py'):
        print("  🥈 АЛЬТЕРНАТИВА: python dokploy_launcher.py")
        print("     • Универсальный launcher")
        print("     • Автоопределение режима запуска")
        print("     • Fallback на раздельные процессы")
    elif os.path.exists('start_production.py'):
        print("  🥉 LEGACY: python start_production.py")
        print("     • Раздельные процессы")
        print("     • Больше потребление ресурсов")
    else:
        print("  ⚠️ Рекомендуемые файлы не найдены")

def main():
    """Основная функция тестирования"""
    print("=" * 60)
    print("🧪 ТЕСТ СИСТЕМЫ ЗАПУСКА - Telegram Channel Finder Bot")
    print("🏗️  Платформа: Railpack/Dokploy")
    print("=" * 60)
    
    # Информация о системе
    print(f"🐍 Python: {sys.version}")
    print(f"📁 Рабочая директория: {os.getcwd()}")
    print(f"🌍 Окружение: {os.getenv('ENVIRONMENT', 'не установлено')}")
    
    # Тесты
    env_ok = test_environment()
    available_files = test_files()
    available_imports = test_imports()
    launch_options = test_launch_options()
    
    # Рекомендации
    recommend_launch_command()
    
    # Итоговый отчет
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ ОТЧЕТ:")
    print("=" * 60)
    
    print(f"✅ Переменные окружения: {'ОК' if env_ok else 'ПРОБЛЕМЫ'}")
    print(f"📁 Доступные файлы: {len(available_files)}")
    print(f"📦 Доступные модули: {len(available_imports)}")
    print(f"🚀 Варианты запуска: {len(launch_options)}")
    
    if env_ok and available_files and available_imports and launch_options:
        print("\n🎉 СИСТЕМА ГОТОВА К ЗАПУСКУ!")
        
        if 'app.py' in available_files:
            print("\n🎯 РЕКОМЕНДУЕМАЯ КОМАНДА ДЛЯ DOKPLOY:")
            print("   Run Command: python app.py")
        else:
            print("\n🎯 АЛЬТЕРНАТИВНАЯ КОМАНДА ДЛЯ DOKPLOY:")
            print("   Run Command: python dokploy_launcher.py")
            
    else:
        print("\n⚠️ ОБНАРУЖЕНЫ ПРОБЛЕМЫ!")
        print("   Проверьте отсутствующие компоненты")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
