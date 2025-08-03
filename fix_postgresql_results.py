#!/usr/bin/env python3
"""
Скрипт для исправления всех result[0] на _extract_count в UniversalDatabase
"""

import re

def fix_universal_database():
    """Исправить все result[0] в UniversalDatabase"""
    
    with open('database/universal_database.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Паттерны для замены
    patterns = [
        # result[0] if result else 0
        (r'(\w+_result)\[0\]\s+if\s+\1\s+else\s+0', r'self._extract_count(\1)'),
        # result[0] if result else default
        (r'(\w+)\[0\]\s+if\s+\1\s+else\s+\d+', r'self._extract_count(\1)'),
        # return result[0] if result else 0
        (r'return\s+(\w+)\[0\]\s+if\s+\1\s+else\s+0', r'return self._extract_count(\1)'),
        # variable = result[0] if result else 0
        (r'(\w+)\s*=\s*(\w+)\[0\]\s+if\s+\2\s+else\s+0', r'\1 = self._extract_count(\2)'),
        # Простые случаи result[0]
        (r'(\w+_result)\[0\](?!\s+if)', r'self._extract_count(\1)'),
    ]
    
    changes_made = 0
    for pattern, replacement in patterns:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            matches = len(re.findall(pattern, content))
            changes_made += matches
            content = new_content
            print(f"✅ Заменено {matches} вхождений: {pattern}")
    
    # Записываем обратно
    with open('database/universal_database.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n🎉 Всего изменений: {changes_made}")
    return changes_made

if __name__ == "__main__":
    print("🔧 Исправление PostgreSQL результатов в UniversalDatabase...")
    changes = fix_universal_database()
    if changes > 0:
        print("✅ Исправления применены! Перезапустите сервисы.")
    else:
        print("ℹ️ Изменений не требуется.")
