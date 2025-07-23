#!/usr/bin/env python3
"""
Скрипт для запуска админ-панели
"""
import uvicorn
from admin.config import HOST, PORT, DEBUG, LOG_LEVEL

if __name__ == "__main__":
    print(f"🚀 Запуск админ-панели на http://{HOST}:{PORT}")
    print(f"📊 Debug режим: {'включен' if DEBUG else 'выключен'}")
    print(f"👤 Админ по умолчанию: admin / admin123")
    print("⚠️  ОБЯЗАТЕЛЬНО смените пароль после первого входа!")
    print("-" * 50)
    
    uvicorn.run(
        "admin.app:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level=LOG_LEVEL.lower()
    )
