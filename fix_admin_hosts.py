#!/usr/bin/env python3
"""
Быстрое исправление настроек хостов для админ-панели
"""
import os
import sys

def fix_admin_config():
    """Исправление конфигурации админ-панели"""
    
    # Устанавливаем правильные переменные окружения
    os.environ["ENVIRONMENT"] = "production"
    os.environ["ADMIN_ALLOWED_HOSTS"] = "*"
    os.environ["ADMIN_CORS_ORIGINS"] = "*"
    os.environ["ADMIN_HOST"] = "0.0.0.0"
    os.environ["ADMIN_PORT"] = "8080"
    
    print("🔧 Исправление настроек админ-панели...")
    print(f"✅ ADMIN_ALLOWED_HOSTS: {os.environ['ADMIN_ALLOWED_HOSTS']}")
    print(f"✅ ADMIN_CORS_ORIGINS: {os.environ['ADMIN_CORS_ORIGINS']}")
    print(f"✅ ADMIN_HOST: {os.environ['ADMIN_HOST']}")
    print(f"✅ ADMIN_PORT: {os.environ['ADMIN_PORT']}")
    
    # Запускаем админ-панель
    try:
        import uvicorn
        from admin.app import app
        
        print("🌐 Запуск админ-панели с исправленными настройками...")
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8080,
            log_level="info",
            access_log=True
        )
        
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
        return False
    
    return True

if __name__ == "__main__":
    fix_admin_config()
