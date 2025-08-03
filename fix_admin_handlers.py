#!/usr/bin/env python3
"""
Скрипт для автоматической замены Database на UniversalDatabase в admin.py
"""

import re

def fix_admin_handlers():
    """Исправить все обработчики в admin.py"""
    
    file_path = 'bot/handlers/admin.py'
    
    try:
        # Читаем файл
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Заменяем все вхождения "db: Database" на "db: UniversalDatabase"
        content = re.sub(r'db: Database', 'db: UniversalDatabase', content)
        
        # Записываем обратно
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Файл {file_path} успешно обновлен")
        
        # Подсчитываем количество замен
        matches = re.findall(r'db: UniversalDatabase', content)
        print(f"📊 Заменено {len(matches)} вхождений")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при обработке файла {file_path}: {e}")
        return False

if __name__ == "__main__":
    print("🔧 ИСПРАВЛЕНИЕ ОБРАБОТЧИКОВ ADMIN.PY")
    print("=" * 50)
    
    success = fix_admin_handlers()
    
    if success:
        print("\n🎉 Все обработчики успешно обновлены!")
    else:
        print("\n❌ Не удалось обновить обработчики")
