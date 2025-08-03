#!/usr/bin/env python3
"""
Скрипт для анализа различий между классами Database и UniversalDatabase
Находит методы, которые есть в Database, но отсутствуют в UniversalDatabase
"""

import ast
import os
from typing import Set, List, Dict

def extract_methods_from_file(file_path: str, class_name: str) -> Set[str]:
    """Извлекает все методы из указанного класса в файле"""
    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        return set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        methods = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                        methods.add(item.name)
                break
        
        return methods
    except Exception as e:
        print(f"❌ Ошибка при анализе файла {file_path}: {e}")
        return set()

def get_method_signatures(file_path: str, class_name: str) -> Dict[str, str]:
    """Получает сигнатуры методов из класса"""
    if not os.path.exists(file_path):
        return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        signatures = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                        # Получаем сигнатуру метода
                        args = []
                        for arg in item.args.args:
                            args.append(arg.arg)
                        
                        signature = f"{'async ' if isinstance(item, ast.AsyncFunctionDef) else ''}def {item.name}({', '.join(args)})"
                        signatures[item.name] = signature
                break
        
        return signatures
    except Exception as e:
        print(f"❌ Ошибка при получении сигнатур из {file_path}: {e}")
        return {}

def analyze_database_differences():
    """Основная функция анализа"""
    print("🔍 Анализ различий между классами Database и UniversalDatabase")
    print("=" * 70)
    
    # Пути к файлам
    database_file = "database/models.py"
    universal_database_file = "database/universal_database.py"
    
    # Извлекаем методы из обоих классов
    print("📋 Извлечение методов из Database...")
    database_methods = extract_methods_from_file(database_file, "Database")
    print(f"   Найдено методов в Database: {len(database_methods)}")
    
    print("📋 Извлечение методов из UniversalDatabase...")
    universal_methods = extract_methods_from_file(universal_database_file, "UniversalDatabase")
    print(f"   Найдено методов в UniversalDatabase: {len(universal_methods)}")
    
    # Находим отсутствующие методы
    missing_methods = database_methods - universal_methods
    extra_methods = universal_methods - database_methods
    common_methods = database_methods & universal_methods
    
    print("\n" + "=" * 70)
    print("📊 РЕЗУЛЬТАТЫ АНАЛИЗА")
    print("=" * 70)
    
    print(f"\n✅ Общие методы ({len(common_methods)}):")
    for method in sorted(common_methods):
        print(f"   • {method}")
    
    print(f"\n❌ Методы отсутствующие в UniversalDatabase ({len(missing_methods)}):")
    if missing_methods:
        # Получаем сигнатуры отсутствующих методов
        database_signatures = get_method_signatures(database_file, "Database")
        
        for method in sorted(missing_methods):
            signature = database_signatures.get(method, f"def {method}(...)")
            print(f"   • {signature}")
    else:
        print("   Все методы присутствуют!")
    
    print(f"\n➕ Дополнительные методы в UniversalDatabase ({len(extra_methods)}):")
    if extra_methods:
        universal_signatures = get_method_signatures(universal_database_file, "UniversalDatabase")
        
        for method in sorted(extra_methods):
            signature = universal_signatures.get(method, f"def {method}(...)")
            print(f"   • {signature}")
    else:
        print("   Дополнительных методов нет")
    
    # Особое внимание к методам платежей
    payment_methods = [m for m in missing_methods if 'payment' in m.lower()]
    if payment_methods:
        print(f"\n💳 КРИТИЧНО - Отсутствующие методы платежей ({len(payment_methods)}):")
        database_signatures = get_method_signatures(database_file, "Database")
        for method in sorted(payment_methods):
            signature = database_signatures.get(method, f"def {method}(...)")
            print(f"   🚨 {signature}")
    
    # Рекомендации
    print("\n" + "=" * 70)
    print("💡 РЕКОМЕНДАЦИИ")
    print("=" * 70)
    
    if missing_methods:
        print(f"\n1. Необходимо добавить {len(missing_methods)} отсутствующих методов в UniversalDatabase")
        print("2. Особое внимание к методам платежей - они критичны для работы системы")
        print("3. После добавления методов перезапустить бота и админ-панель")
    else:
        print("\n✅ Все методы присутствуют, проблема может быть в другом")
    
    return {
        'missing_methods': missing_methods,
        'extra_methods': extra_methods,
        'common_methods': common_methods,
        'payment_methods': payment_methods
    }

if __name__ == "__main__":
    try:
        results = analyze_database_differences()
        
        print(f"\n📈 СТАТИСТИКА:")
        print(f"   • Отсутствующих методов: {len(results['missing_methods'])}")
        print(f"   • Дополнительных методов: {len(results['extra_methods'])}")
        print(f"   • Общих методов: {len(results['common_methods'])}")
        print(f"   • Критичных методов платежей: {len(results['payment_methods'])}")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения скрипта: {e}")
        import traceback
        traceback.print_exc()
