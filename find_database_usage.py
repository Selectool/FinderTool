#!/usr/bin/env python3
"""
Скрипт для поиска всех файлов, которые используют Database класс
"""

import os
import re
from pathlib import Path

def find_database_usage():
    """Найти все файлы, которые используют Database класс"""
    
    # Паттерны для поиска
    patterns = [
        r'from database\.models import Database',
        r'db: Database',
        r'Database\(',
        r'aiosqlite\.connect',
        r'self\.db_path'
    ]
    
    # Директории для поиска
    search_dirs = ['bot/', 'database/', 'admin/', 'services/']
    
    results = {}
    
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue
            
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        matches = []
                        for pattern in patterns:
                            pattern_matches = re.findall(pattern, content)
                            if pattern_matches:
                                matches.extend([(pattern, len(pattern_matches))])
                        
                        if matches:
                            results[file_path] = matches
                            
                    except Exception as e:
                        print(f"❌ Ошибка чтения файла {file_path}: {e}")
    
    return results

def main():
    print("🔍 ПОИСК ИСПОЛЬЗОВАНИЯ DATABASE КЛАССА")
    print("=" * 60)
    
    results = find_database_usage()
    
    if not results:
        print("✅ Не найдено файлов с использованием Database класса")
        return
    
    print(f"📊 Найдено {len(results)} файлов с использованием Database:")
    print()
    
    for file_path, matches in results.items():
        print(f"📁 {file_path}:")
        for pattern, count in matches:
            print(f"   - {pattern}: {count} вхождений")
        print()
    
    # Рекомендации
    print("💡 РЕКОМЕНДАЦИИ:")
    print("1. Замените 'from database.models import Database' на 'from database.universal_database import UniversalDatabase'")
    print("2. Замените 'db: Database' на 'db: UniversalDatabase'")
    print("3. Замените 'Database(' на 'UniversalDatabase('")
    print("4. Удалите использование 'aiosqlite.connect' и 'self.db_path'")

if __name__ == "__main__":
    main()
