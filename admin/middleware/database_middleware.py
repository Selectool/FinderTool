"""
Production-ready Database Middleware для FastAPI
Обеспечивает стабильное управление соединениями с базой данных
"""

import logging
import time
import os
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from database.universal_database import UniversalDatabase

# Безопасная функция для получения переменной окружения
def get_environment():
    """Получить переменную окружения с fallback"""
    try:
        return os.getenv("ENVIRONMENT", "production")
    except Exception:
        return "production"

# Глобальная переменная для кэширования
_ENVIRONMENT_CACHE = None

def get_cached_environment():
    """Получить кэшированную переменную окружения"""
    global _ENVIRONMENT_CACHE
    if _ENVIRONMENT_CACHE is None:
        _ENVIRONMENT_CACHE = get_environment()
    return _ENVIRONMENT_CACHE

logger = logging.getLogger(__name__)

class DatabaseConnectionMiddleware(BaseHTTPMiddleware):
    """
    Production-ready middleware для управления соединениями с базой данных
    
    Функциональность:
    - Автоматическое переподключение при потере соединения
    - Мониторинг здоровья соединений
    - Логирование проблем с базой данных
    - Graceful handling ошибок соединения
    """
    
    def __init__(self, app, database_url: str):
        super().__init__(app)
        self.database_url = database_url
        self.db_instance = None
        self.connection_errors = 0
        self.last_error_time = 0
        self.max_connection_errors = 5
        self.error_reset_interval = 300  # 5 минут
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Обработка запроса с управлением соединением БД"""
        start_time = time.time()
        
        try:
            # Получаем или создаем экземпляр базы данных
            db = await self._get_database_instance()
            
            # Проверяем здоровье соединения
            await self._ensure_healthy_connection(db)
            
            # Добавляем БД в состояние запроса
            request.state.db = db
            
            # Выполняем запрос
            response = await call_next(request)
            
            # Сбрасываем счетчик ошибок при успешном запросе
            if self.connection_errors > 0:
                self.connection_errors = 0
                logger.info("✅ Соединение с базой данных восстановлено")
            
            return response
            
        except Exception as e:
            # Обрабатываем ошибки соединения
            await self._handle_database_error(e)
            
            # Создаем fallback response
            return await self._create_error_response(request, e)
            
        finally:
            # Логируем время выполнения
            execution_time = time.time() - start_time
            if execution_time > 1.0:  # Логируем медленные запросы
                logger.warning(f"⏱️ Медленный запрос к БД: {execution_time:.2f}s для {request.url.path}")
    
    async def _get_database_instance(self) -> UniversalDatabase:
        """Получить экземпляр базы данных"""
        if not self.db_instance:
            self.db_instance = UniversalDatabase(self.database_url)
            logger.debug("🔧 Создан новый экземпляр UniversalDatabase")
        
        return self.db_instance
    
    async def _ensure_healthy_connection(self, db: UniversalDatabase):
        """Убедиться, что соединение с БД здоровое"""
        try:
            # Проверяем соединение
            if not db.adapter.connection or db.adapter.connection.is_closed():
                logger.debug("🔄 Переподключение к базе данных...")
                await db.adapter.connect()
            
            # Простой health check
            await db.adapter.fetch_one("SELECT 1 as health_check")
            
        except Exception as e:
            logger.error(f"❌ Проблема с соединением БД: {e}")
            # Пытаемся переподключиться
            try:
                await db.adapter.connect()
                logger.info("✅ Успешное переподключение к БД")
            except Exception as reconnect_error:
                logger.error(f"❌ Не удалось переподключиться к БД: {reconnect_error}")
                raise
    
    async def _handle_database_error(self, error: Exception):
        """Обработка ошибок базы данных"""
        current_time = time.time()

        # Увеличиваем счетчик ошибок
        self.connection_errors += 1
        self.last_error_time = current_time

        # Безопасное логирование ошибки
        try:
            logger.error(f"❌ Ошибка базы данных #{self.connection_errors}: {error}")
        except Exception as log_error:
            # Если даже логирование не работает, используем print
            print(f"❌ Ошибка базы данных #{self.connection_errors}: {error}")
            print(f"❌ Ошибка логирования: {log_error}")

        # Если слишком много ошибок, сбрасываем соединение
        if self.connection_errors >= self.max_connection_errors:
            try:
                logger.error(f"🚨 Критическое количество ошибок БД ({self.connection_errors}), сброс соединения")
            except:
                print(f"🚨 Критическое количество ошибок БД ({self.connection_errors}), сброс соединения")

            if self.db_instance:
                try:
                    await self.db_instance.adapter.disconnect()
                except:
                    pass
                self.db_instance = None
        
        # Сбрасываем счетчик ошибок через интервал
        if current_time - self.last_error_time > self.error_reset_interval:
            self.connection_errors = 0
            logger.info("🔄 Сброс счетчика ошибок БД")
    
    async def _create_error_response(self, request: Request, error: Exception) -> Response:
        """Создать ответ об ошибке"""
        from fastapi.responses import JSONResponse
        
        # Определяем тип ошибки
        if "connection" in str(error).lower() or "closed" in str(error).lower():
            error_message = "Временные проблемы с базой данных. Попробуйте позже."
            status_code = 503  # Service Unavailable
        else:
            error_message = "Внутренняя ошибка сервера"
            status_code = 500
        
        # Для API запросов возвращаем JSON
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": error_message,
                    "details": "Database connection issue" if status_code == 503 else "Internal server error",
                    "timestamp": time.time()
                }
            )
        
        # Для веб-страниц возвращаем HTML
        from fastapi.responses import HTMLResponse
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Ошибка сервера</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .error {{ color: #d32f2f; }}
                .retry {{ margin-top: 20px; }}
            </style>
        </head>
        <body>
            <h1 class="error">⚠️ {error_message}</h1>
            <p>Мы работаем над устранением проблемы.</p>
            <div class="retry">
                <button onclick="window.location.reload()">Попробовать снова</button>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content, status_code=status_code)

class DatabaseHealthCheck:
    """Утилита для проверки здоровья базы данных"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.db = UniversalDatabase(database_url)
    
    async def check_health(self) -> dict:
        """Проверить здоровье базы данных"""
        try:
            start_time = time.time()
            
            # Проверяем соединение
            await self.db.adapter.connect()
            
            # Выполняем тестовый запрос
            result = await self.db.adapter.fetch_one("SELECT 1 as test, NOW() as current_time")
            
            response_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "database_time": str(result.get("current_time")) if result else None,
                "connection_status": "active",
                "timestamp": time.time()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "connection_status": "failed",
                "timestamp": time.time()
            }
        
        finally:
            try:
                await self.db.adapter.disconnect()
            except:
                pass

# Глобальный экземпляр для health checks
_health_checker = None

def get_health_checker(database_url: str = None) -> DatabaseHealthCheck:
    """Получить экземпляр health checker"""
    global _health_checker
    if not _health_checker and database_url:
        _health_checker = DatabaseHealthCheck(database_url)
    return _health_checker
