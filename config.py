"""
Конфигурация бота
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot API
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения! Добавьте его в .env файл")

# Telegram API для Telethon
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# База данных (только PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL обязательна! Укажите PostgreSQL URL в переменных окружения.")
if not (DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://')):
    raise ValueError("Поддерживается только PostgreSQL. DATABASE_URL должен начинаться с 'postgresql://' или 'postgres://'.")

# Админ настройки
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

# Разработчики (имеют безлимитный доступ)
DEVELOPER_IDS = [5699315855]  # ID разработчика

# Production-ready настройки подписки
SUBSCRIPTION_PRICE = int(os.getenv("SUBSCRIPTION_PRICE", "500"))  # Обновленная цена
FREE_REQUESTS_LIMIT = int(os.getenv("FREE_REQUESTS_LIMIT", "3"))

# Настройки безопасности для production
MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "10"))
MAX_REQUESTS_PER_HOUR = int(os.getenv("MAX_REQUESTS_PER_HOUR", "100"))
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"

# Production Environment Detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# ЮKassa настройки - Production-ready конфигурация
YOOKASSA_MODE = "LIVE" if IS_PRODUCTION else os.getenv("YOOKASSA_MODE", "TEST")

# Токены ЮKassa с поддержкой современных форматов
YOOKASSA_TEST_TOKEN = os.getenv("YOOKASSA_TEST_TOKEN", "381764678:TEST:132745")
YOOKASSA_LIVE_TOKEN = os.getenv("YOOKASSA_LIVE_TOKEN", "live_O2uh0MKZesYawcyTyiT6WMlV3IeDfIULnZTkVt5cQW0")

# Основные настройки ЮKassa
YOOKASSA_CURRENCY = os.getenv("YOOKASSA_CURRENCY", "RUB")
YOOKASSA_PRODUCT_DESCRIPTION = os.getenv("YOOKASSA_PRODUCT_DESCRIPTION", "Подписка FinderTool на месяц")
YOOKASSA_VAT_CODE = int(os.getenv("YOOKASSA_VAT_CODE", "1"))

# Получение активного токена в зависимости от режима
YOOKASSA_PROVIDER_TOKEN = YOOKASSA_LIVE_TOKEN if YOOKASSA_MODE == "LIVE" else YOOKASSA_TEST_TOKEN

def validate_yookassa_token(token: str, mode: str) -> bool:
    """Валидация токена ЮKassa с поддержкой современных форматов"""
    if not token:
        return False

    if mode == "LIVE":
        # Поддержка как старого формата (xxx:LIVE:xxx), так и нового (live_xxx)
        return ":LIVE:" in token or token.startswith("live_")
    elif mode == "TEST":
        # Поддержка как старого формата (xxx:TEST:xxx), так и нового (test_xxx)
        return ":TEST:" in token or token.startswith("test_")

    return False

# Production-ready проверка токенов
if YOOKASSA_MODE == "LIVE":
    if not YOOKASSA_LIVE_TOKEN:
        raise ValueError("LIVE режим требует установки YOOKASSA_LIVE_TOKEN")
    if not validate_yookassa_token(YOOKASSA_LIVE_TOKEN, "LIVE"):
        raise ValueError("LIVE токен имеет неверный формат. Ожидается формат 'live_xxx' или 'xxx:LIVE:xxx'")

if YOOKASSA_MODE == "TEST":
    if not YOOKASSA_TEST_TOKEN:
        raise ValueError("TEST режим требует установки YOOKASSA_TEST_TOKEN")
    if not validate_yookassa_token(YOOKASSA_TEST_TOKEN, "TEST"):
        raise ValueError("TEST токен имеет неверный формат. Ожидается формат 'test_xxx' или 'xxx:TEST:xxx'")

# Данные для формирования чека (provider_data) - исправленный формат для Telegram Bot API
YOOKASSA_PROVIDER_DATA = json.dumps({
    "receipt": {
        "items": [
            {
                "description": YOOKASSA_PRODUCT_DESCRIPTION,
                "quantity": "1.00",
                "amount": {
                    "value": f"{SUBSCRIPTION_PRICE:.2f}",
                    "currency": YOOKASSA_CURRENCY
                },
                "vat_code": YOOKASSA_VAT_CODE,
                "payment_mode": "full_payment",
                "payment_subject": "service"
            }
        ],
        "customer": {
            "email": "support@findertool.ru"
        }
    }
}, ensure_ascii=False)

# Production-ready логирование
import logging
logger = logging.getLogger(__name__)

# Безопасное логирование без утечки sensitive данных
def safe_log_token(token: str) -> str:
    """Безопасное логирование токена без раскрытия sensitive данных"""
    if not token:
        return "НЕ УСТАНОВЛЕН"
    if token.startswith("live_"):
        return f"live_***{token[-4:]}"
    elif token.startswith("test_"):
        return f"test_***{token[-4:]}"
    elif ":" in token:
        parts = token.split(":")
        return f"{parts[0]}:***:{parts[-1]}" if len(parts) >= 3 else "***"
    return "***"

# Production-ready логирование конфигурации
logger.info(f"🚀 Запуск в режиме: {ENVIRONMENT.upper()}")
logger.info(f"💳 ЮKassa режим: {YOOKASSA_MODE}")
logger.info(f"🔑 Активный токен: {safe_log_token(YOOKASSA_PROVIDER_TOKEN)}")

if IS_PRODUCTION:
    logger.warning("⚠️ ВНИМАНИЕ: PRODUCTION режим - реальные платежи и данные!")
    logger.info("🔒 Включены production security меры")
else:
    logger.info("🧪 Development режим - тестовые платежи")

# Валидация критически важных настроек для production
if IS_PRODUCTION:
    critical_vars = {
        "BOT_TOKEN": BOT_TOKEN,
        "DATABASE_URL": DATABASE_URL,
        "YOOKASSA_LIVE_TOKEN": YOOKASSA_LIVE_TOKEN,
        "API_ID": API_ID,
        "API_HASH": API_HASH
    }

    missing_vars = [var for var, value in critical_vars.items() if not value or (isinstance(value, int) and value == 0)]

    if missing_vars:
        raise ValueError(f"❌ Production режим требует установки переменных: {', '.join(missing_vars)}")

    logger.info("✅ Все критически важные переменные настроены для production")

# Сессия Telethon
SESSION_NAME = os.getenv("SESSION_NAME", "bot_session")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# Тексты бота
TEXTS = {
    "start": """
🤖 <b>Добро пожаловать в FinderTool!</b>

Я помогу вам найти похожие каналы в Telegram.

📝 <b>Как пользоваться:</b>
• Отправьте ссылку на канал (или несколько ссылок)
• Получите список похожих каналов

💎 <b>Лимиты:</b>
• 3 бесплатных запроса
• Безлимитная подписка: {price}₽/месяц

Используйте /help для получения помощи.
    """,
    
    "help": """
📖 <b>Справка по использованию бота</b>

<b>Команды:</b>
/start - Начать работу с ботом
/help - Показать эту справку
/profile - Ваш профиль и статистика
/subscribe - Оформить подписку

<b>Как найти похожие каналы:</b>
1. Отправьте ссылку на канал (например: https://t.me/channel_name)
2. Можете отправить несколько ссылок в одном сообщении
3. Получите список похожих каналов

<b>Поддерживаемые форматы ссылок:</b>
• https://t.me/channel_name
• @channel_name
• t.me/channel_name

💬 По вопросам обращайтесь к администратору.
    """,
    
    "no_requests_left": """
😔 <b>Лимит исчерпан</b>

У вас закончились бесплатные запросы ({limit} из {limit}).

💎 Оформите подписку за {price}₽/месяц для безлимитного использования!

/subscribe - Оформить подписку
    """,
    
    "processing": "🔍 Ищу похожие каналы...",
    
    "no_channels_found": "😔 Похожие каналы не найдены для указанных ссылок.",
    
    "invalid_link": "❌ Неверная ссылка на канал: {link}",
    
    "error": "❌ Произошла ошибка. Попробуйте позже.",
    
    "subscription_info": """
💎 <b>Подписка FinderTool</b>

<b>Стоимость:</b> {price}₽/месяц
<b>Преимущества:</b>
• Безлимитные запросы
• Приоритетная поддержка
• Новые функции первыми

Нажмите кнопку ниже для оплаты:
    """
}

# Production-ready настройки ЮKassa API
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "390540012")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY",
    "live_MjkwNTQwMDEyOmxpdmVfTzJ1aDBNS1plc1lhd2N5VHlpVDZXTWxWM0llRGZJVUxuWlRrVnQ1Y1FXMCIsImFjY291bnRfaWQiOiI5MDU0MDAxMiIsInNob3BfaWQiOiIzOTA1NDAwMTIifQ=="
    if IS_PRODUCTION else "test_Fh8hUAVVBGUGbjmlzba6TB0iyUbos_lueTHE-axOwM0")

YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "https://t.me/FinderToolBot")

# Настройки комиссий ЮKassa (актуальные на 2025 год)
YOOKASSA_COMMISSIONS = {
    'bank_card': 2.9,      # Банковские карты
    'yoo_money': 2.9,      # ЮMoney
    'sberbank': 2.9,       # Сбербанк Онлайн
    'sbp': 0.4,            # Система быстрых платежей (СБП)
    'qiwi': 3.5,           # QIWI Кошелек
    'webmoney': 3.5,       # WebMoney
    'alfabank': 2.9,       # Альфа-Клик
    'tinkoff_bank': 2.9,   # Тинькофф
    'default': 2.9
}

# Базовая цена подписки
SUBSCRIPTION_BASE_PRICE = float(SUBSCRIPTION_PRICE)

# Production monitoring и health check настройки
HEALTH_CHECK_ENABLED = os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true"
METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() == "true"
ERROR_REPORTING_ENABLED = os.getenv("ERROR_REPORTING_ENABLED", "true").lower() == "true"

# Timeout настройки для production
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))  # секунд
DATABASE_TIMEOUT = int(os.getenv("DATABASE_TIMEOUT", "10"))  # секунд
PAYMENT_TIMEOUT = int(os.getenv("PAYMENT_TIMEOUT", "60"))  # секунд

# Безопасное логирование финальной конфигурации
logger.info(f"💰 Цена подписки: {SUBSCRIPTION_BASE_PRICE}₽")
logger.info(f"🏪 ЮKassa Shop ID: {YOOKASSA_SHOP_ID}")
logger.info(f"🔒 Rate limiting: {'включен' if RATE_LIMIT_ENABLED else 'отключен'}")
logger.info(f"📊 Мониторинг: {'включен' if HEALTH_CHECK_ENABLED else 'отключен'}")
logger.info(f"⏱️ Таймауты: запросы={REQUEST_TIMEOUT}с, БД={DATABASE_TIMEOUT}с, платежи={PAYMENT_TIMEOUT}с")
