#!/usr/bin/env python3
"""
Скрипт для автоматического исправления всех файлов, использующих Database класс
"""

import os
import re
from pathlib import Path

def fix_file(file_path):
    """Исправить один файл"""
    try:
        # Читаем файл
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Замены
        replacements = [
            # Импорты
            (r'from database\.models import Database', 'from database.universal_database import UniversalDatabase'),
            # Типы параметров
            (r'db: Database', 'db: UniversalDatabase'),
            # Создание экземпляров
            (r'Database\(', 'UniversalDatabase('),
        ]
        
        changes_made = 0
        for pattern, replacement in replacements:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                changes_made += len(re.findall(pattern, content))
                content = new_content
        
        # Записываем обратно только если были изменения
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return changes_made
        
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка при обработке файла {file_path}: {e}")
        return -1

def main():
    print("🔧 АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ DATABASE USAGE")
    print("=" * 60)
    
    # Файлы для исправления (исключаем некоторые системные файлы)
    exclude_files = {
        'database/models.py',  # Оставляем как есть для совместимости
        'database/db_adapter.py',  # Системный файл
        'database/monitoring.py',  # Системный файл
        'database/backup_system.py',  # Системный файл
        'database/admin_migrations.py',  # Legacy файл
        'database/reset_manager.py',  # Legacy файл
        'database/universal_database.py',  # Наш новый файл
    }
    
    # Директории для поиска
    search_dirs = ['bot/', 'admin/', 'services/']
    
    total_files = 0
    total_changes = 0
    
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue
            
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file).replace('\\', '/')
                    
                    # Пропускаем исключенные файлы
                    if file_path in exclude_files:
                        continue
                    
                    changes = fix_file(file_path)
                    if changes > 0:
                        total_files += 1
                        total_changes += changes
                        print(f"✅ {file_path}: {changes} изменений")
                    elif changes == -1:
                        print(f"❌ {file_path}: ошибка")
    
    print()
    print(f"📊 ИТОГО:")
    print(f"   - Обработано файлов: {total_files}")
    print(f"   - Всего изменений: {total_changes}")
    
    if total_changes > 0:
        print()
        print("🎉 Все файлы успешно обновлены!")
        print("📝 Следующие шаги:")
        print("   1. Перезапустите бота для применения изменений")
        print("   2. Проверьте логи на наличие ошибок")
        print("   3. Протестируйте основные функции")
    else:
        print("\n✅ Все файлы уже актуальны!")

if __name__ == "__main__":
    main()
