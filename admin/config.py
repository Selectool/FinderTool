"""
Конфигурация админ-панели с автоматическим определением окружения
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Определение окружения
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Загрузка соответствующего .env файла
if ENVIRONMENT == "development":
    env_file = ".env.development"
elif ENVIRONMENT == "production":
    env_file = ".env"
else:
    env_file = ".env"

# Проверяем существование файла конфигурации
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"📁 Загружена конфигурация: {env_file}")
else:
    load_dotenv()  # Загружаем дефолтный .env
    print(f"⚠️  Файл {env_file} не найден, используется .env")

# Переопределяем ENVIRONMENT после загрузки .env
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Основные настройки с учетом окружения
if ENVIRONMENT == "development":
    DEFAULT_SECRET_KEY = "your-super-secret-key-change-in-production"
    DEFAULT_DEBUG = "True"
    DEFAULT_HOST = "127.0.0.1"
else:
    DEFAULT_SECRET_KEY = "your-super-secret-key-change-in-production"
    DEFAULT_DEBUG = "False"
    DEFAULT_HOST = "0.0.0.0"

SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", DEFAULT_SECRET_KEY)
DEBUG = os.getenv("ADMIN_DEBUG", DEFAULT_DEBUG).lower() == "true"
HOST = os.getenv("ADMIN_HOST", DEFAULT_HOST)
PORT = int(os.getenv("ADMIN_PORT", "8080"))

# JWT настройки с учетом окружения
if ENVIRONMENT == "development":
    DEFAULT_JWT_SECRET = "your-jwt-secret-key-change-in-production"
    DEFAULT_ACCESS_EXPIRE = "60"  # 1 час для разработки
    DEFAULT_REFRESH_EXPIRE = "30"  # 30 дней для разработки
else:
    DEFAULT_JWT_SECRET = SECRET_KEY
    DEFAULT_ACCESS_EXPIRE = "30"  # 30 минут для продакшн
    DEFAULT_REFRESH_EXPIRE = "7"  # 7 дней для продакшн

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEFAULT_JWT_SECRET)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", DEFAULT_ACCESS_EXPIRE))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", DEFAULT_REFRESH_EXPIRE))

# ============ SECURITY VALIDATION ============
def validate_security_keys():
    """Валидация ключей безопасности для production-ready системы"""
    import secrets
    import hashlib

    # Проверяем длину и сложность JWT ключа
    if len(JWT_SECRET_KEY) < 32:
        if ENVIRONMENT == "production":
            raise ValueError("JWT_SECRET_KEY должен быть минимум 32 символа для production!")
        else:
            print("⚠️  ПРЕДУПРЕЖДЕНИЕ: JWT_SECRET_KEY слишком короткий для production")

    # Проверяем, что не используются дефолтные ключи в production
    default_patterns = [
        "dev-", "test-", "auto-generated", "change-in-production",
        "your-", "secret-key", "jwt-secret"
    ]

    if ENVIRONMENT == "production":
        for pattern in default_patterns:
            if pattern in JWT_SECRET_KEY.lower() or pattern in SECRET_KEY.lower():
                raise ValueError(f"Обнаружен небезопасный паттерн '{pattern}' в ключах безопасности! "
                               f"Измените ключи для production!")

    # Проверяем энтропию ключей
    jwt_entropy = len(set(JWT_SECRET_KEY))
    if jwt_entropy < 16:
        if ENVIRONMENT == "production":
            raise ValueError("JWT_SECRET_KEY имеет низкую энтропию! Используйте более случайный ключ.")
        else:
            print(f"⚠️  ПРЕДУПРЕЖДЕНИЕ: JWT_SECRET_KEY имеет низкую энтропию ({jwt_entropy} уникальных символов)")

    print(f"🔐 Валидация ключей безопасности: {'✅ ПРОЙДЕНА' if ENVIRONMENT != 'production' or jwt_entropy >= 16 else '❌ ПРОВАЛЕНА'}")

# Выполняем валидацию при загрузке модуля
validate_security_keys()

# База данных (только PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL обязательна! Укажите PostgreSQL URL в переменных окружения.")
if not (DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://')):
    raise ValueError("Поддерживается только PostgreSQL. DATABASE_URL должен начинаться с 'postgresql://' или 'postgres://'.")

# Рассылки
BROADCAST_RATE_LIMIT = int(os.getenv("BROADCAST_RATE_LIMIT", "30"))  # сообщений в минуту
BROADCAST_BATCH_SIZE = int(os.getenv("BROADCAST_BATCH_SIZE", "100"))
BROADCAST_RETRY_ATTEMPTS = int(os.getenv("BROADCAST_RETRY_ATTEMPTS", "3"))

# Уведомления
NOTIFICATION_WEBHOOK_URL = os.getenv("NOTIFICATION_WEBHOOK_URL", "")
NOTIFICATION_EMAIL_SMTP = os.getenv("NOTIFICATION_EMAIL_SMTP", "")

# Telegram Bot (для отправки рассылок)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Безопасность с учетом окружения
if ENVIRONMENT == "development":
    DEFAULT_ALLOWED_HOSTS = "127.0.0.1,localhost"
    DEFAULT_CORS_ORIGINS = "http://localhost:8080,http://127.0.0.1:8080"
else:
    DEFAULT_ALLOWED_HOSTS = "*"
    DEFAULT_CORS_ORIGINS = "https://your-domain.com"

ALLOWED_HOSTS = os.getenv("ADMIN_ALLOWED_HOSTS", DEFAULT_ALLOWED_HOSTS).split(",")
CORS_ORIGINS = os.getenv("ADMIN_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")

# Логирование
LOG_LEVEL = os.getenv("ADMIN_LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("ADMIN_LOG_FILE", "admin.log")

# Пагинация
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "50"))
MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "200"))

# Файлы
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB

# Дополнительные настройки безопасности
SKIP_SSL_VERIFY = os.getenv("SKIP_SSL_VERIFY", "False").lower() == "true"
ENABLE_DEBUG_ROUTES = os.getenv("ENABLE_DEBUG_ROUTES", "False").lower() == "true"
MOCK_PAYMENTS = os.getenv("MOCK_PAYMENTS", "False").lower() == "true"

# Создаем папку для загрузок если не существует
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Валидация конфигурации при импорте
def validate_config():
    """Валидация конфигурации при запуске"""
    try:
        from admin.utils.config_validator import ConfigValidator, auto_fix_dev_config

        # Собираем текущую конфигурацию
        config_dict = {
            "ENVIRONMENT": ENVIRONMENT,
            "BOT_TOKEN": BOT_TOKEN,
            "API_ID": os.getenv("API_ID"),
            "API_HASH": os.getenv("API_HASH"),
            "ADMIN_USER_ID": os.getenv("ADMIN_USER_ID"),
            "ADMIN_SECRET_KEY": SECRET_KEY,
            "ADMIN_HOST": HOST,
            "ADMIN_PORT": PORT,
            "ADMIN_DEBUG": DEBUG,
            "ADMIN_ALLOWED_HOSTS": ",".join(ALLOWED_HOSTS),
            "ADMIN_CORS_ORIGINS": ",".join(CORS_ORIGINS),
            "JWT_SECRET_KEY": JWT_SECRET_KEY,
            "JWT_ALGORITHM": JWT_ALGORITHM,
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            "JWT_REFRESH_TOKEN_EXPIRE_DAYS": JWT_REFRESH_TOKEN_EXPIRE_DAYS,
            "DATABASE_URL": DATABASE_URL,
            "YOOKASSA_MODE": os.getenv("YOOKASSA_MODE", "TEST"),
            "YOOKASSA_SHOP_ID": os.getenv("YOOKASSA_SHOP_ID"),
            "YOOKASSA_SECRET_KEY": os.getenv("YOOKASSA_SECRET_KEY"),
            "SKIP_SSL_VERIFY": SKIP_SSL_VERIFY,
            "ENABLE_DEBUG_ROUTES": ENABLE_DEBUG_ROUTES,
            "MOCK_PAYMENTS": MOCK_PAYMENTS,
        }

        # Автоматическое исправление для разработки
        if ENVIRONMENT == "development":
            config_dict = auto_fix_dev_config(config_dict)
            # Обновляем глобальные переменные
            globals()["SECRET_KEY"] = config_dict["ADMIN_SECRET_KEY"]
            globals()["JWT_SECRET_KEY"] = config_dict["JWT_SECRET_KEY"]

        # Валидация
        validator = ConfigValidator(ENVIRONMENT)
        is_valid = validator.validate_all(config_dict)

        # Вывод отчета
        report = validator.get_report()
        if report:
            print("🔧 ПРОВЕРКА КОНФИГУРАЦИИ:")
            print(report)
            print("-" * 50)

        if not is_valid and ENVIRONMENT == "production":
            print("❌ КРИТИЧЕСКИЕ ОШИБКИ КОНФИГУРАЦИИ В ПРОДАКШН РЕЖИМЕ!")
            print("Исправьте ошибки перед запуском.")
            sys.exit(1)

    except ImportError:
        print("⚠️  Валидатор конфигурации недоступен")
    except Exception as e:
        print(f"⚠️  Ошибка валидации конфигурации: {e}")

# Запускаем валидацию при импорте модуля
validate_config()

# Информация о текущем окружении
print(f"🌍 Окружение: {ENVIRONMENT}")
print(f"🏠 Хост админ-панели: {HOST}:{PORT}")
print(f"🔧 Режим отладки: {'включен' if DEBUG else 'выключен'}")
if ENVIRONMENT == "development":
    print("🔑 Автоматически сгенерированы безопасные ключи для разработки")
