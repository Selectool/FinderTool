"""
Конфигурация бота
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot API
BOT_TOKEN = os.getenv("BOT_TOKEN", "8066350716:AAHEDXC0kL_L-TXui8vxI0HhD0wchIzl1hI")

# Telegram API для Telethon
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# База данных
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot.db")

# Админ настройки
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

# Разработчики (имеют безлимитный доступ)
DEVELOPER_IDS = [5699315855]  # ID разработчика

# Настройки подписки
SUBSCRIPTION_PRICE = int(os.getenv("SUBSCRIPTION_PRICE", "349"))
FREE_REQUESTS_LIMIT = int(os.getenv("FREE_REQUESTS_LIMIT", "3"))

# ЮKassa настройки
YOOKASSA_MODE = os.getenv("YOOKASSA_MODE", "TEST")
YOOKASSA_TEST_TOKEN = os.getenv("YOOKASSA_TEST_TOKEN", "381764678:TEST:132745")
YOOKASSA_LIVE_TOKEN = os.getenv("YOOKASSA_LIVE_TOKEN", "390540012:LIVE:74136")
YOOKASSA_CURRENCY = os.getenv("YOOKASSA_CURRENCY", "RUB")
YOOKASSA_PRODUCT_DESCRIPTION = os.getenv("YOOKASSA_PRODUCT_DESCRIPTION", "Подписка Channel Finder Bot на месяц")
YOOKASSA_VAT_CODE = int(os.getenv("YOOKASSA_VAT_CODE", "1"))

# Получение активного токена в зависимости от режима
YOOKASSA_PROVIDER_TOKEN = YOOKASSA_TEST_TOKEN if YOOKASSA_MODE == "TEST" else YOOKASSA_LIVE_TOKEN

# Проверка корректности токена для выбранного режима
if YOOKASSA_MODE == "LIVE" and not YOOKASSA_LIVE_TOKEN:
    raise ValueError("LIVE режим требует установки YOOKASSA_LIVE_TOKEN")
if YOOKASSA_MODE == "TEST" and not YOOKASSA_TEST_TOKEN:
    raise ValueError("TEST режим требует установки YOOKASSA_TEST_TOKEN")

# Проверка формата токена
if YOOKASSA_MODE == "LIVE" and ":LIVE:" not in YOOKASSA_LIVE_TOKEN:
    raise ValueError("LIVE токен должен содержать ':LIVE:' для продакшн режима")
if YOOKASSA_MODE == "TEST" and ":TEST:" not in YOOKASSA_TEST_TOKEN:
    raise ValueError("TEST токен должен содержать ':TEST:' для тестового режима")

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

# Логирование текущего режима ЮKassa
import logging
logger = logging.getLogger(__name__)
logger.info(f"ЮKassa режим: {YOOKASSA_MODE}")
if YOOKASSA_MODE == "LIVE":
    logger.warning("⚠️ ВНИМАНИЕ: Работа в ПРОДАКШН режиме с реальными платежами!")
else:
    logger.info("🧪 Работа в тестовом режиме ЮKassa")

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

# Окружение
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Настройки комиссий ЮKassa (в процентах)
YOOKASSA_COMMISSIONS = {
    'bank_card': 3.5,
    'yoo_money': 3.5,
    'sberbank': 3.5,
    'sbp': 0.7,  # Система быстрых платежей
    'qiwi': 6.0,
    'default': 3.5
}

# Дополнительные настройки ЮKassa для API
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "390540012")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "test_Fh8hUAVVBGUGbjmlzba6TB0iyUbos_lueTHE-axOwM0")
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "https://t.me/FinderToolBot")

# Базовая цена подписки (без комиссии)
SUBSCRIPTION_BASE_PRICE = 349.00  # рублей

logger.info(f"Базовая цена подписки: {SUBSCRIPTION_BASE_PRICE}₽")
logger.info(f"Комиссии ЮKassa: {YOOKASSA_COMMISSIONS}")
logger.info(f"ЮKassa Shop ID: {YOOKASSA_SHOP_ID}")
