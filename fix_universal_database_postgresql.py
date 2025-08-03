#!/usr/bin/env python3
"""
Production-ready исправление UniversalDatabase для PostgreSQL
"""

import re
import os

def fix_universal_database():
    """Исправить все проблемы с PostgreSQL в UniversalDatabase"""
    
    file_path = 'database/universal_database.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Создаем backup
    with open(f'{file_path}.backup', 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Исправления для PostgreSQL
    fixes = [
        # Исправляем все result[0] на _extract_count для COUNT запросов
        (r'(\w+_result)\[0\]\s+if\s+\1\s+else\s+0', r'self._extract_count(\1)'),
        (r'return\s+(\w+)\[0\]\s+if\s+\1\s+else\s+0', r'return self._extract_count(\1)'),
        (r'(\w+)\s*=\s*(\w+)\[0\]\s+if\s+\2\s+else\s+0', r'\1 = self._extract_count(\2)'),
        
        # Исправляем прямые обращения к result[0] в COUNT запросах
        (r'(count_result|total_result|users_result|subs_result|active_result)\[0\]', r'self._extract_count(\1)'),
        
        # Исправляем условные блоки с result
        (r'if\s+(\w+):\s*\n\s*#[^\n]*\n\s*if\s+hasattr\(\1,\s*\'__getitem__\'\)[^}]+count\s*=\s*\1\[0\][^}]+else:[^}]+count\s*=\s*\1', 
         r'if \1:\n                count = self._extract_count(\1)'),
        
        # Исправляем блоки обработки результатов
        (r'if\s+result\s+is\s+not\s+None:\s*\n\s*#[^{]+\{\s*\n[^}]+result\[0\][^}]+\}', 
         r'if result is not None:\n                count = self._extract_count(result)'),
    ]
    
    changes_made = 0
    for pattern, replacement in fixes:
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
        if new_content != content:
            matches = len(re.findall(pattern, content, flags=re.MULTILINE | re.DOTALL))
            changes_made += matches
            content = new_content
            print(f"✅ Исправлено {matches} вхождений")
    
    # Специальные исправления для конкретных методов
    specific_fixes = [
        # get_users_count
        (r'result\s*=\s*await\s+self\.adapter\.fetch_one\("SELECT COUNT\(\*\) FROM users"\)\s*\n\s*await\s+self\.adapter\.disconnect\(\)\s*\n\s*return\s+result\[0\]\s+if\s+result\s+else\s+0',
         'result = await self.adapter.fetch_one("SELECT COUNT(*) FROM users")\n            await self.adapter.disconnect()\n            return self._extract_count(result)'),
        
        # get_active_users_count
        (r'result\s*=\s*await\s+self\.adapter\.fetch_one\(query\)\s*\n\s*await\s+self\.adapter\.disconnect\(\)\s*\n\s*return\s+result\[0\]\s+if\s+result\s+else\s+0',
         'result = await self.adapter.fetch_one(query)\n            await self.adapter.disconnect()\n            return self._extract_count(result)'),
        
        # get_subscribers_count
        (r'result\s*=\s*await\s+self\.adapter\.fetch_one\(query\)\s*\n\s*await\s+self\.adapter\.disconnect\(\)\s*\n\s*return\s+result\[0\]\s+if\s+result\s+else\s+0',
         'result = await self.adapter.fetch_one(query)\n            await self.adapter.disconnect()\n            return self._extract_count(result)'),
    ]
    
    for pattern, replacement in specific_fixes:
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
        if new_content != content:
            changes_made += 1
            content = new_content
            print(f"✅ Исправлен специфический метод")
    
    # Записываем исправленный файл
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n🎉 Всего исправлений: {changes_made}")
    print(f"📁 Backup сохранен: {file_path}.backup")
    return changes_made

def apply_manual_fixes():
    """Применить ручные исправления для критических методов"""
    
    file_path = 'database/universal_database.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Ручные исправления для методов, которые не поймал regex
    manual_fixes = [
        # Исправляем get_stats метод
        ('stats[\'total_users\'] = total_users_result[0] if total_users_result else 0',
         'stats[\'total_users\'] = self._extract_count(total_users_result)'),
        
        ('stats[\'active_subscribers\'] = active_subs_result[0] if active_subs_result else 0',
         'stats[\'active_subscribers\'] = self._extract_count(active_subs_result)'),
        
        ('stats[\'requests_today\'] = requests_today_result[0] if requests_today_result else 0',
         'stats[\'requests_today\'] = self._extract_count(requests_today_result)'),
        
        # Исправляем другие методы
        ('return result[0] if result else 0',
         'return self._extract_count(result)'),
    ]
    
    changes_made = 0
    for old_text, new_text in manual_fixes:
        if old_text in content:
            content = content.replace(old_text, new_text)
            changes_made += 1
            print(f"✅ Исправлено: {old_text[:50]}...")
    
    # Записываем обратно
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"🔧 Ручных исправлений: {changes_made}")
    return changes_made

if __name__ == "__main__":
    print("🚀 Production-ready исправление UniversalDatabase для PostgreSQL...")
    
    auto_changes = fix_universal_database()
    manual_changes = apply_manual_fixes()
    
    total_changes = auto_changes + manual_changes
    
    if total_changes > 0:
        print(f"\n✅ Всего исправлений: {total_changes}")
        print("🔄 Перезапустите сервисы для применения изменений")
    else:
        print("\nℹ️ Изменений не требуется")
    
    print("\n📋 Следующие шаги:")
    print("1. Запустите миграцию: python -c \"from database.migration_manager import MigrationManager; import asyncio; asyncio.run(MigrationManager().migrate())\"")
    print("2. Перезапустите бота: python main.py")
    print("3. Перезапустите админ-панель: python run_admin.py")
