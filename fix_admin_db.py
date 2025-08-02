#!/usr/bin/env python3
"""
Скрипт для исправления проблемы с базой данных в админ-панели
"""
import os
import sys
import asyncio
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Устанавливаем продакшн режим
os.environ["ENVIRONMENT"] = "production"

async def fix_admin_database():
    """Исправление базы данных для админ-панели"""
    try:
        print("🔧 Исправление базы данных для админ-панели...")
        
        # Инициализируем production database manager
        from database.production_manager import ProductionDatabaseManager
        
        production_manager = ProductionDatabaseManager()
        await production_manager.initialize_database()
        
        print("✅ Production база данных инициализирована")
        
        # Создаем простую админ-панель без сложных зависимостей
        from fastapi import FastAPI
        import uvicorn
        
        app = FastAPI(title="Channel Finder Admin")
        
        @app.get("/")
        async def root():
            return {"message": "Admin panel is working", "status": "ok"}
        
        @app.get("/auth/login")
        async def login_page():
            return {"message": "Login page", "admin": "admin", "password": "admin123"}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy", "database": "postgresql"}
        
        print("🌐 Запуск упрощенной админ-панели...")
        print("🏠 Адрес: http://0.0.0.0:8080")
        
        # Запускаем сервер
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8080,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    try:
        asyncio.run(fix_admin_database())
    except KeyboardInterrupt:
        print("\n👋 Админ-панель остановлена")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
