#!/usr/bin/env python3
"""
Автоматическое исправление UniversalDatabase
Добавляет все отсутствующие методы из Database в UniversalDatabase
"""

import ast
import os
import re
from typing import List, Dict, Set

def extract_method_code(file_path: str, class_name: str, method_name: str) -> str:
    """Извлекает код метода из файла с улучшенным парсингом"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Находим начало класса
        class_start = -1
        for i, line in enumerate(lines):
            if line.strip().startswith(f'class {class_name}'):
                class_start = i
                break

        if class_start == -1:
            return ""

        # Находим метод в классе
        method_start = -1
        for i in range(class_start, len(lines)):
            line = lines[i].strip()
            if (line.startswith(f'async def {method_name}(') or
                line.startswith(f'def {method_name}(')):
                method_start = i
                break

        if method_start == -1:
            return ""

        # Находим конец метода (следующий метод или конец класса)
        method_end = len(lines)
        base_indent = len(lines[method_start]) - len(lines[method_start].lstrip())

        for i in range(method_start + 1, len(lines)):
            line = lines[i]
            if line.strip() == "":
                continue

            current_indent = len(line) - len(line.lstrip())

            # Если отступ меньше или равен базовому и это не комментарий
            if (current_indent <= base_indent and
                line.strip() and
                not line.strip().startswith('#') and
                not line.strip().startswith('"""') and
                not line.strip().startswith("'''")):
                method_end = i
                break

        # Извлекаем код метода
        method_lines = lines[method_start:method_end]
        return ''.join(method_lines).rstrip()

    except Exception as e:
        print(f"❌ Ошибка извлечения метода {method_name}: {e}")
        return ""

def get_missing_methods() -> List[str]:
    """Получает список отсутствующих методов"""
    return [
        'create_payment',
        'get_payment', 
        'complete_payment',
        'get_user_payments',
        'update_payment_status',
        'create_admin_user',
        'get_admin_users',
        'log_admin_action',
        'get_audit_logs',
        'create_message_template',
        'get_message_templates',
        'get_message_template',
        'update_message_template',
        'get_broadcast_by_id',
        'get_broadcasts_list',
        'get_broadcasts_stats',
        'get_broadcast_detailed_stats',
        'get_broadcast_logs',
        'get_all_broadcast_logs',
        'log_broadcast_delivery',
        'update_broadcast_status',
        'update_broadcast_stats',
        'get_broadcast_target_users',
        'get_target_audience_count',
        'get_detailed_stats',
        'get_users_paginated',
        'get_all_users',
        'get_active_users',
        'get_subscribers',
        'get_users_by_role',
        'get_user_activity_chart_data',
        'get_blocked_users_count',
        'delete_user',
        'bulk_delete_users',
        'mark_user_bot_blocked',
        'update_user_bot_blocked_status',
        'update_user_permissions',
        'update_user_role',
        'update_subscription',
        'reset_user_requests',
        '_run_migrations'
    ]

def convert_sqlite_to_universal(method_code: str) -> str:
    """Конвертирует SQLite код в универсальный для работы с адаптером"""

    # Простая замена основных паттернов
    lines = method_code.split('\n')
    new_lines = []

    for line in lines:
        # Заменяем aiosqlite.connect
        if 'async with aiosqlite.connect(self.db_path) as db:' in line:
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f'{indent}try:')
            new_lines.append(f'{indent}    await self.adapter.connect()')
            continue

        # Заменяем db операции
        line = re.sub(r'\bdb\.execute\b', 'self.adapter.execute', line)
        line = re.sub(r'\bdb\.commit\b', '# commit handled by adapter', line)
        line = re.sub(r'\bdb\.fetchone\b', 'self.adapter.fetch_one', line)
        line = re.sub(r'\bdb\.fetchall\b', 'self.adapter.fetch_all', line)
        line = re.sub(r'\bdb\.row_factory = aiosqlite\.Row', '# row_factory handled by adapter', line)

        # Заменяем cursor операции
        if 'cursor = await' in line and 'db.execute' in line:
            line = re.sub(r'cursor = await db\.execute\((.*?)\)', r'await self.adapter.execute(\1)', line)

        if 'cursor.lastrowid' in line:
            line = re.sub(r'cursor\.lastrowid', 'self.adapter.lastrowid', line)

        new_lines.append(line)

    # Добавляем finally блок в конец
    if any('await self.adapter.connect()' in line for line in new_lines):
        # Находим базовый отступ метода
        method_indent = ''
        for line in new_lines:
            if line.strip().startswith('async def') or line.strip().startswith('def'):
                method_indent = line[:len(line) - len(line.lstrip())]
                break

        # Добавляем обработку ошибок
        new_lines.append(f'{method_indent}except Exception as e:')
        new_lines.append(f'{method_indent}    logger.error(f"Ошибка в методе: {{e}}")')
        new_lines.append(f'{method_indent}    try:')
        new_lines.append(f'{method_indent}        await self.adapter.disconnect()')
        new_lines.append(f'{method_indent}    except:')
        new_lines.append(f'{method_indent}        pass')
        new_lines.append(f'{method_indent}    raise')
        new_lines.append(f'{method_indent}finally:')
        new_lines.append(f'{method_indent}    try:')
        new_lines.append(f'{method_indent}        await self.adapter.disconnect()')
        new_lines.append(f'{method_indent}    except:')
        new_lines.append(f'{method_indent}        pass')

    return '\n'.join(new_lines)

def add_missing_methods():
    """Добавляет отсутствующие методы в UniversalDatabase"""
    print("🔧 Автоматическое исправление UniversalDatabase...")
    
    database_file = "database/models.py"
    universal_file = "database/universal_database.py"
    
    if not os.path.exists(database_file):
        print(f"❌ Файл {database_file} не найден")
        return False
    
    if not os.path.exists(universal_file):
        print(f"❌ Файл {universal_file} не найден")
        return False
    
    # Читаем текущий UniversalDatabase
    with open(universal_file, 'r', encoding='utf-8') as f:
        universal_content = f.read()
    
    # Получаем список методов для добавления
    missing_methods = get_missing_methods()
    
    print(f"📋 Добавление {len(missing_methods)} отсутствующих методов...")
    
    # Создаем резервную копию
    backup_file = f"{universal_file}.backup"
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(universal_content)
    print(f"💾 Создана резервная копия: {backup_file}")
    
    # Добавляем методы
    methods_to_add = []
    
    for method_name in missing_methods:
        print(f"   🔍 Извлечение метода {method_name}...")
        method_code = extract_method_code(database_file, "Database", method_name)
        
        if method_code:
            # Конвертируем в универсальный формат
            universal_method = convert_sqlite_to_universal(method_code)
            methods_to_add.append(universal_method)
            print(f"   ✅ Метод {method_name} подготовлен")
        else:
            print(f"   ⚠️ Метод {method_name} не найден в Database")
    
    # Добавляем методы в конец класса (перед последней строкой)
    if methods_to_add:
        # Находим конец класса UniversalDatabase
        lines = universal_content.split('\n')
        
        # Ищем последний метод класса
        insert_position = len(lines) - 1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() and not lines[i].startswith(' ') and not lines[i].startswith('\t'):
                insert_position = i
                break
        
        # Добавляем новые методы
        new_content_lines = lines[:insert_position]
        
        # Добавляем комментарий
        new_content_lines.append("")
        new_content_lines.append("    # ========== АВТОМАТИЧЕСКИ ДОБАВЛЕННЫЕ МЕТОДЫ ==========")
        new_content_lines.append("")
        
        # Добавляем методы
        for method_code in methods_to_add:
            new_content_lines.extend(method_code.split('\n'))
            new_content_lines.append("")
        
        # Добавляем оставшиеся строки
        new_content_lines.extend(lines[insert_position:])
        
        # Записываем обновленный файл
        new_content = '\n'.join(new_content_lines)
        
        with open(universal_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ Добавлено {len(methods_to_add)} методов в {universal_file}")
        return True
    else:
        print("❌ Не удалось извлечь методы для добавления")
        return False

if __name__ == "__main__":
    try:
        success = add_missing_methods()
        
        if success:
            print("\n🎉 ИСПРАВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!")
            print("📋 Следующие шаги:")
            print("   1. Проверьте добавленные методы в universal_database.py")
            print("   2. Перезапустите бота и админ-панель")
            print("   3. Протестируйте функциональность платежей")
        else:
            print("\n❌ Исправление не удалось")
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
