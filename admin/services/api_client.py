"""
Production-ready API клиент для админ-панели
Поддерживает локальную и удаленную аутентификацию с fallback механизмами
"""
import os
import asyncio
import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
import httpx
from fastapi import HTTPException, status
import ssl

logger = logging.getLogger(__name__)


class APIClientConfig:
    """Конфигурация API клиента"""
    
    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8080")
        self.fallback_url = os.getenv("API_FALLBACK_URL", "http://185.207.66.201:8080")
        self.timeout = float(os.getenv("API_TIMEOUT", "30"))
        self.retry_attempts = int(os.getenv("API_RETRY_ATTEMPTS", "3"))
        self.ssl_verify = os.getenv("API_SSL_VERIFY", "True").lower() == "true"
        self.use_local_auth = os.getenv("API_USE_LOCAL_AUTH", "True").lower() == "true"
        
        # Настройки для продакшена
        if self.environment == "production":
            self.ssl_verify = True
            self.timeout = 60
            self.retry_attempts = 5
        
        logger.info(f"🔧 API Client Config: env={self.environment}, base={self.base_url}, ssl_verify={self.ssl_verify}")


class ProductionAPIClient:
    """Production-ready API клиент с fallback механизмами"""
    
    def __init__(self):
        self.config = APIClientConfig()
        self._health_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300  # 5 минут
        
        # Настройки SSL для продакшена
        self.ssl_context = None
        if self.config.ssl_verify and self.config.environment == "production":
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = True
            self.ssl_context.verify_mode = ssl.CERT_REQUIRED
    
    async def _check_endpoint_health(self, url: str) -> bool:
        """Проверка доступности endpoint"""
        # Для локальной разработки пропускаем health check, чтобы избежать циклических запросов
        if self.config.environment == "development" and url == self.config.base_url:
            logger.debug(f"🔧 Пропускаем health check для локального endpoint: {url}")
            return True

        cache_key = f"health_{url}"
        now = datetime.now()

        # Проверяем кэш
        if cache_key in self._health_cache:
            cache_data = self._health_cache[cache_key]
            if now - cache_data["timestamp"] < timedelta(seconds=self._cache_ttl):
                return cache_data["healthy"]

        try:
            async with httpx.AsyncClient(
                timeout=5.0,
                verify=self.config.ssl_verify
            ) as client:
                response = await client.get(f"{url}/health", timeout=5.0)
                healthy = response.status_code == 200

                # Кэшируем результат
                self._health_cache[cache_key] = {
                    "healthy": healthy,
                    "timestamp": now
                }

                return healthy

        except Exception as e:
            logger.warning(f"⚠️ Health check failed for {url}: {e}")
            # Кэшируем негативный результат на меньшее время
            self._health_cache[cache_key] = {
                "healthy": False,
                "timestamp": now - timedelta(seconds=self._cache_ttl - 60)
            }
            return False
    
    async def _get_available_endpoints(self) -> List[str]:
        """Получить список доступных endpoints в порядке приоритета"""
        endpoints = []
        
        # Проверяем основной endpoint
        if await self._check_endpoint_health(self.config.base_url):
            endpoints.append(self.config.base_url)
            logger.debug(f"✅ Primary endpoint available: {self.config.base_url}")
        
        # Проверяем fallback endpoint
        if self.config.fallback_url and self.config.fallback_url != self.config.base_url:
            if await self._check_endpoint_health(self.config.fallback_url):
                endpoints.append(self.config.fallback_url)
                logger.debug(f"✅ Fallback endpoint available: {self.config.fallback_url}")
        
        if not endpoints:
            logger.error("❌ No healthy endpoints available")
        
        return endpoints
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> httpx.Response:
        """Выполнить HTTP запрос с retry механизмом"""
        
        available_endpoints = await self._get_available_endpoints()
        
        if not available_endpoints:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Все API серверы недоступны"
            )
        
        last_exception = None
        
        for attempt in range(self.config.retry_attempts):
            for base_url in available_endpoints:
                try:
                    url = f"{base_url}{endpoint}"
                    
                    async with httpx.AsyncClient(
                        timeout=self.config.timeout,
                        verify=self.config.ssl_verify
                    ) as client:
                        
                        if method.upper() == "GET":
                            response = await client.get(url, headers=headers, **kwargs)
                        elif method.upper() == "POST":
                            response = await client.post(url, json=data, headers=headers, **kwargs)
                        elif method.upper() == "PUT":
                            response = await client.put(url, json=data, headers=headers, **kwargs)
                        elif method.upper() == "DELETE":
                            response = await client.delete(url, headers=headers, **kwargs)
                        else:
                            raise ValueError(f"Unsupported HTTP method: {method}")
                        
                        # Логируем успешный запрос
                        logger.debug(f"✅ API request successful: {method} {url} -> {response.status_code}")
                        return response
                        
                except httpx.TimeoutException as e:
                    last_exception = e
                    logger.warning(f"⏱️ Timeout for {base_url}: attempt {attempt + 1}/{self.config.retry_attempts}")
                    
                except httpx.ConnectError as e:
                    last_exception = e
                    logger.warning(f"🔌 Connection error for {base_url}: {e}")
                    # Помечаем endpoint как недоступный
                    cache_key = f"health_{base_url}"
                    self._health_cache[cache_key] = {
                        "healthy": False,
                        "timestamp": datetime.now()
                    }
                    
                except Exception as e:
                    last_exception = e
                    logger.error(f"❌ Unexpected error for {base_url}: {e}")
            
            # Пауза между попытками
            if attempt < self.config.retry_attempts - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        # Все попытки исчерпаны
        logger.error(f"❌ All API requests failed after {self.config.retry_attempts} attempts")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"API недоступен: {str(last_exception)}"
        )
    
    async def authenticate(self, username: str, password: str) -> Dict[str, Any]:
        """Аутентификация пользователя"""

        # Для локальной разработки ВСЕГДА используем прямой вызов, чтобы избежать циклических запросов
        if self.config.environment == "development":
            try:
                logger.info(f"🔧 Используем локальную аутентификацию для {username}")
                return await self._local_authenticate(username, password)
            except Exception as e:
                logger.error(f"❌ Local auth failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Ошибка локальной аутентификации"
                )

        # API аутентификация для продакшена
        try:
            response = await self._make_request(
                "POST",
                "/api/auth/login",
                data={"username": username, "password": password}
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Неверное имя пользователя или пароль"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Ошибка аутентификации: {response.text}"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Сервис аутентификации недоступен"
            )
    
    async def _local_authenticate(self, username: str, password: str) -> Dict[str, Any]:
        """Локальная аутентификация (для разработки)"""
        try:
            from ..auth.auth import authenticate_user, create_tokens
            from database.universal_database import UniversalDatabase
            
            db = UniversalDatabase()
            user = await authenticate_user(db, username, password)
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Неверное имя пользователя или пароль"
                )
            
            if not user["is_active"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Аккаунт деактивирован"
                )
            
            tokens = create_tokens(user)
            logger.info(f"✅ Local authentication successful for user: {username}")
            return tokens
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Local authentication error: {e}")
            raise


# Глобальный экземпляр API клиента
api_client = ProductionAPIClient()
