"""
Конфигурация админ-панели
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Основные настройки
SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "your-super-secret-key-change-in-production")
DEBUG = os.getenv("ADMIN_DEBUG", "False").lower() == "true"
HOST = os.getenv("ADMIN_HOST", "127.0.0.1")
PORT = int(os.getenv("ADMIN_PORT", "8080"))

# JWT настройки
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# База данных
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot.db")
DATABASE_PATH = DATABASE_URL.replace("sqlite:///", "")

# Рассылки
BROADCAST_RATE_LIMIT = int(os.getenv("BROADCAST_RATE_LIMIT", "30"))  # сообщений в минуту
BROADCAST_BATCH_SIZE = int(os.getenv("BROADCAST_BATCH_SIZE", "100"))
BROADCAST_RETRY_ATTEMPTS = int(os.getenv("BROADCAST_RETRY_ATTEMPTS", "3"))

# Уведомления
NOTIFICATION_WEBHOOK_URL = os.getenv("NOTIFICATION_WEBHOOK_URL", "")
NOTIFICATION_EMAIL_SMTP = os.getenv("NOTIFICATION_EMAIL_SMTP", "")

# Telegram Bot (для отправки рассылок)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Безопасность
ALLOWED_HOSTS = os.getenv("ADMIN_ALLOWED_HOSTS", "*").split(",")
CORS_ORIGINS = os.getenv("ADMIN_CORS_ORIGINS", "http://localhost:8080").split(",")

# Логирование
LOG_LEVEL = os.getenv("ADMIN_LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("ADMIN_LOG_FILE", "admin.log")

# Пагинация
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "50"))
MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "200"))

# Файлы
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB

# Создаем папку для загрузок если не существует
os.makedirs(UPLOAD_DIR, exist_ok=True)
