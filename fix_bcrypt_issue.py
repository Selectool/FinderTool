#!/usr/bin/env python3
"""
Быстрое исправление проблемы с bcrypt
"""
import subprocess
import sys
import os

def fix_bcrypt():
    """Исправить проблему с bcrypt"""
    print("🔧 Исправление проблемы с bcrypt...")
    
    try:
        # Обновляем bcrypt до совместимой версии
        commands = [
            "pip uninstall -y bcrypt",
            "pip install bcrypt==4.0.1",
            "pip install --upgrade passlib"
        ]
        
        for cmd in commands:
            print(f"Выполняем: {cmd}")
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            if result.returncode != 0:
                print(f"⚠️ Предупреждение: {result.stderr}")
            else:
                print(f"✅ Успешно: {result.stdout}")
        
        print("✅ Проблема с bcrypt исправлена")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка исправления bcrypt: {e}")
        return False

def restart_services():
    """Перезапустить сервисы"""
    print("🔄 Перезапуск сервисов...")
    
    try:
        # Останавливаем процессы
        stop_commands = [
            "pkill -f 'python main.py'",
            "pkill -f 'python run_admin.py'",
            "pkill -f 'python start_with_migrations.py'"
        ]
        
        for cmd in stop_commands:
            try:
                subprocess.run(cmd.split(), capture_output=True)
            except:
                pass
        
        print("🛑 Старые процессы остановлены")
        
        # Запускаем с миграциями
        print("🚀 Запуск с исправленным bcrypt...")
        subprocess.Popen([sys.executable, "start_with_migrations.py"])
        
        print("✅ Сервисы перезапущены")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка перезапуска: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Быстрое исправление проблемы с bcrypt...")
    
    if fix_bcrypt():
        restart_services()
        print("🎉 Исправление завершено!")
        print("🌐 Админ-панель: http://185.207.66.201:8080")
        print("🔑 Логин: admin / admin123")
    else:
        print("❌ Не удалось исправить проблему")
        sys.exit(1)
