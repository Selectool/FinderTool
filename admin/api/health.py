"""
Health check endpoints для мониторинга состояния API
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
import os
import psutil
import time
from datetime import datetime
import logging

from database.universal_database import UniversalDatabase

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_db(request: Request) -> UniversalDatabase:
    """Получить объект базы данных"""
    return request.state.db


@router.get("/health")
async def health_check():
    """Базовая проверка здоровья сервиса"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "telegram-channel-finder-admin",
            "environment": os.getenv("ENVIRONMENT", "unknown")
        }
    )


@router.get("/health/detailed")
async def detailed_health_check(db: UniversalDatabase = Depends(get_db)):
    """Детальная проверка здоровья всех компонентов"""
    
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "telegram-channel-finder-admin",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "components": {}
    }
    
    overall_healthy = True
    
    # Проверка базы данных
    try:
        start_time = time.time()
        # Простой запрос для проверки подключения
        await db.execute_query("SELECT 1")
        db_response_time = (time.time() - start_time) * 1000
        
        health_data["components"]["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_response_time, 2),
            "type": "postgresql"
        }
    except Exception as e:
        overall_healthy = False
        health_data["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
            "type": "postgresql"
        }
    
    # Проверка системных ресурсов
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        health_data["components"]["system"] = {
            "status": "healthy",
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "disk_percent": disk.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2)
        }
        
        # Предупреждения о высокой нагрузке
        if cpu_percent > 80 or memory.percent > 85 or disk.percent > 90:
            health_data["components"]["system"]["warnings"] = []
            if cpu_percent > 80:
                health_data["components"]["system"]["warnings"].append(f"High CPU usage: {cpu_percent}%")
            if memory.percent > 85:
                health_data["components"]["system"]["warnings"].append(f"High memory usage: {memory.percent}%")
            if disk.percent > 90:
                health_data["components"]["system"]["warnings"].append(f"High disk usage: {disk.percent}%")
                
    except Exception as e:
        health_data["components"]["system"] = {
            "status": "unknown",
            "error": str(e)
        }
    
    # Проверка конфигурации
    try:
        required_env_vars = [
            "BOT_TOKEN", "API_ID", "API_HASH", "DATABASE_URL",
            "ADMIN_SECRET_KEY", "JWT_SECRET_KEY"
        ]
        
        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            overall_healthy = False
            health_data["components"]["configuration"] = {
                "status": "unhealthy",
                "missing_variables": missing_vars
            }
        else:
            health_data["components"]["configuration"] = {
                "status": "healthy",
                "environment": os.getenv("ENVIRONMENT"),
                "debug_mode": os.getenv("ADMIN_DEBUG", "False").lower() == "true"
            }
            
    except Exception as e:
        health_data["components"]["configuration"] = {
            "status": "unknown",
            "error": str(e)
        }
    
    # Проверка Telegram API (опционально)
    try:
        bot_token = os.getenv("BOT_TOKEN")
        if bot_token:
            # Здесь можно добавить проверку доступности Telegram API
            health_data["components"]["telegram"] = {
                "status": "configured",
                "bot_token_present": True
            }
        else:
            health_data["components"]["telegram"] = {
                "status": "not_configured",
                "bot_token_present": False
            }
    except Exception as e:
        health_data["components"]["telegram"] = {
            "status": "unknown",
            "error": str(e)
        }
    
    # Общий статус
    if not overall_healthy:
        health_data["status"] = "unhealthy"
    
    # Определяем HTTP статус код
    status_code = 200 if overall_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content=health_data
    )


@router.get("/health/ready")
async def readiness_check(db: UniversalDatabase = Depends(get_db)):
    """Проверка готовности к обслуживанию запросов"""
    
    try:
        # Проверяем критически важные компоненты
        await db.execute_query("SELECT 1")
        
        # Проверяем наличие обязательных переменных окружения
        required_vars = ["BOT_TOKEN", "DATABASE_URL", "ADMIN_SECRET_KEY"]
        for var in required_vars:
            if not os.getenv(var):
                raise Exception(f"Missing required environment variable: {var}")
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "ready",
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@router.get("/health/live")
async def liveness_check():
    """Проверка жизнеспособности сервиса"""
    
    try:
        # Базовая проверка - сервис отвечает
        return JSONResponse(
            status_code=200,
            content={
                "status": "alive",
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": time.time() - psutil.Process().create_time()
            }
        )
        
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "dead",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )
