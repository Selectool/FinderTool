"""
Валидатор конфигурации для админ-панели
"""
import os
import secrets
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Валидатор конфигурации с проверками безопасности"""
    
    def __init__(self, environment: str = "development"):
        self.environment = environment
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def validate_all(self, config: Dict[str, Any]) -> bool:
        """Валидация всей конфигурации"""
        self.errors.clear()
        self.warnings.clear()
        
        # Основные проверки
        self._validate_required_fields(config)
        self._validate_security_settings(config)
        self._validate_database_settings(config)
        self._validate_admin_panel_settings(config)
        self._validate_jwt_settings(config)
        self._validate_yookassa_settings(config)
        
        # Проверки для продакшн
        if self.environment == "production":
            self._validate_production_security(config)
            
        return len(self.errors) == 0
    
    def _validate_required_fields(self, config: Dict[str, Any]) -> None:
        """Проверка обязательных полей"""
        required_fields = [
            "BOT_TOKEN", "API_ID", "API_HASH", "ADMIN_USER_ID",
            "ADMIN_SECRET_KEY", "JWT_SECRET_KEY"
        ]
        
        for field in required_fields:
            if not config.get(field):
                self.errors.append(f"Обязательное поле {field} не установлено")
    
    def _validate_security_settings(self, config: Dict[str, Any]) -> None:
        """Проверка настроек безопасности"""
        # Проверка секретных ключей
        admin_secret = config.get("ADMIN_SECRET_KEY", "")
        jwt_secret = config.get("JWT_SECRET_KEY", "")
        
        if admin_secret in ["your-super-secret-admin-key-change-in-production", "dev-secret-key-auto-generated"]:
            if self.environment == "production":
                self.errors.append("ADMIN_SECRET_KEY должен быть изменен в продакшн")
            else:
                self.warnings.append("Используется дефолтный ADMIN_SECRET_KEY для разработки")
        
        if jwt_secret in ["your-jwt-secret-key-change-in-production", "dev-jwt-secret-auto-generated"]:
            if self.environment == "production":
                self.errors.append("JWT_SECRET_KEY должен быть изменен в продакшн")
            else:
                self.warnings.append("Используется дефолтный JWT_SECRET_KEY для разработки")
        
        # Проверка длины ключей
        if len(admin_secret) < 32:
            self.warnings.append("ADMIN_SECRET_KEY слишком короткий (рекомендуется минимум 32 символа)")
        
        if len(jwt_secret) < 32:
            self.warnings.append("JWT_SECRET_KEY слишком короткий (рекомендуется минимум 32 символа)")
    
    def _validate_database_settings(self, config: Dict[str, Any]) -> None:
        """Проверка настроек базы данных"""
        db_url = config.get("DATABASE_URL", "")
        
        if not db_url:
            self.errors.append("DATABASE_URL не установлен")
            return
        
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            db_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else "."
            
            if not os.access(db_dir, os.W_OK):
                self.errors.append(f"Нет прав записи в директорию базы данных: {db_dir}")
    
    def _validate_admin_panel_settings(self, config: Dict[str, Any]) -> None:
        """Проверка настроек админ-панели"""
        host = config.get("ADMIN_HOST", "127.0.0.1")
        port = config.get("ADMIN_PORT", 8080)
        debug = config.get("ADMIN_DEBUG", False)
        
        # Проверка хоста
        if self.environment == "production" and host == "0.0.0.0":
            allowed_hosts = config.get("ADMIN_ALLOWED_HOSTS", "")
            if not allowed_hosts or allowed_hosts == "*":
                self.errors.append("В продакшн режиме с ADMIN_HOST=0.0.0.0 необходимо указать ADMIN_ALLOWED_HOSTS")
        
        if self.environment == "development" and host == "0.0.0.0":
            self.warnings.append("В режиме разработки рекомендуется использовать ADMIN_HOST=127.0.0.1")
        
        # Проверка порта
        try:
            port = int(port)
            if port < 1024 and os.getuid() != 0:  # Только для Unix-систем
                self.warnings.append(f"Порт {port} требует root привилегий")
        except (ValueError, AttributeError):
            self.errors.append("ADMIN_PORT должен быть числом")
        
        # Проверка debug режима
        if self.environment == "production" and debug:
            self.errors.append("ADMIN_DEBUG должен быть False в продакшн режиме")
    
    def _validate_jwt_settings(self, config: Dict[str, Any]) -> None:
        """Проверка настроек JWT"""
        algorithm = config.get("JWT_ALGORITHM", "HS256")
        access_expire = config.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
        refresh_expire = config.get("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)
        
        if algorithm not in ["HS256", "HS384", "HS512"]:
            self.warnings.append(f"Неизвестный JWT алгоритм: {algorithm}")
        
        try:
            access_expire = int(access_expire)
            if access_expire > 1440:  # 24 часа
                self.warnings.append("JWT_ACCESS_TOKEN_EXPIRE_MINUTES слишком большой (>24 часов)")
        except ValueError:
            self.errors.append("JWT_ACCESS_TOKEN_EXPIRE_MINUTES должен быть числом")
        
        try:
            refresh_expire = int(refresh_expire)
            if refresh_expire > 90:  # 3 месяца
                self.warnings.append("JWT_REFRESH_TOKEN_EXPIRE_DAYS слишком большой (>90 дней)")
        except ValueError:
            self.errors.append("JWT_REFRESH_TOKEN_EXPIRE_DAYS должен быть числом")
    
    def _validate_yookassa_settings(self, config: Dict[str, Any]) -> None:
        """Проверка настроек ЮKassa"""
        mode = config.get("YOOKASSA_MODE", "TEST")
        shop_id = config.get("YOOKASSA_SHOP_ID", "")
        secret_key = config.get("YOOKASSA_SECRET_KEY", "")
        
        if mode not in ["TEST", "LIVE"]:
            self.errors.append("YOOKASSA_MODE должен быть TEST или LIVE")
        
        if mode == "LIVE":
            if not shop_id:
                self.errors.append("YOOKASSA_SHOP_ID обязателен в LIVE режиме")
            if not secret_key:
                self.errors.append("YOOKASSA_SECRET_KEY обязателен в LIVE режиме")
            if secret_key.startswith("test_"):
                self.errors.append("В LIVE режиме используется тестовый YOOKASSA_SECRET_KEY")
        
        if self.environment == "development" and mode == "LIVE":
            self.warnings.append("В режиме разработки рекомендуется использовать YOOKASSA_MODE=TEST")
    
    def _validate_production_security(self, config: Dict[str, Any]) -> None:
        """Дополнительные проверки безопасности для продакшн"""
        # Проверка CORS
        cors_origins = config.get("ADMIN_CORS_ORIGINS", "")
        if "*" in cors_origins:
            self.errors.append("В продакшн режиме нельзя использовать '*' в ADMIN_CORS_ORIGINS")
        
        # Проверка SSL
        skip_ssl = config.get("SKIP_SSL_VERIFY", False)
        if skip_ssl:
            self.errors.append("SKIP_SSL_VERIFY должен быть False в продакшн режиме")
        
        # Проверка debug маршрутов
        debug_routes = config.get("ENABLE_DEBUG_ROUTES", False)
        if debug_routes:
            self.errors.append("ENABLE_DEBUG_ROUTES должен быть False в продакшн режиме")
        
        # Проверка mock платежей
        mock_payments = config.get("MOCK_PAYMENTS", False)
        if mock_payments:
            self.errors.append("MOCK_PAYMENTS должен быть False в продакшн режиме")
    
    def get_report(self) -> str:
        """Получить отчет о валидации"""
        report = []
        
        if self.errors:
            report.append("❌ ОШИБКИ КОНФИГУРАЦИИ:")
            for error in self.errors:
                report.append(f"  • {error}")
        
        if self.warnings:
            report.append("⚠️  ПРЕДУПРЕЖДЕНИЯ:")
            for warning in self.warnings:
                report.append(f"  • {warning}")
        
        if not self.errors and not self.warnings:
            report.append("✅ Конфигурация валидна")
        
        return "\n".join(report)


def generate_secure_key(length: int = 64) -> str:
    """Генерация безопасного ключа"""
    return secrets.token_urlsafe(length)


def auto_fix_dev_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Автоматическое исправление конфигурации для разработки"""
    fixed_config = config_dict.copy()
    
    # Генерируем безопасные ключи для разработки
    if fixed_config.get("ADMIN_SECRET_KEY") == "dev-secret-key-auto-generated":
        fixed_config["ADMIN_SECRET_KEY"] = generate_secure_key()
    
    if fixed_config.get("JWT_SECRET_KEY") == "dev-jwt-secret-auto-generated":
        fixed_config["JWT_SECRET_KEY"] = generate_secure_key()
    
    return fixed_config
