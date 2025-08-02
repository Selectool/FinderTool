#!/usr/bin/env python3
"""
Тест API админ-панели
"""
import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from admin.app import app
    print("✅ FastAPI app with users API created successfully")
    
    # Проверяем роутеры
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append(f"{list(route.methods)[0]} {route.path}")
    
    print(f"📋 Доступные маршруты ({len(routes)}):")
    for route in sorted(routes):
        print(f"  - {route}")
        
    print("\n🎯 API endpoints для пользователей:")
    user_routes = [r for r in routes if '/api/users' in r]
    for route in user_routes:
        print(f"  - {route}")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
