"""
Конфигурация бота
"""
import os
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
SUBSCRIPTION_PRICE = int(os.getenv("SUBSCRIPTION_PRICE", "500"))
FREE_REQUESTS_LIMIT = int(os.getenv("FREE_REQUESTS_LIMIT", "3"))

# Сессия Telethon
SESSION_NAME = os.getenv("SESSION_NAME", "bot_session")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# Тексты бота
TEXTS = {
    "start": """
🤖 <b>Добро пожаловать в Channel Finder Bot!</b>

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
💎 <b>Подписка Channel Finder Bot</b>

<b>Стоимость:</b> {price}₽/месяц
<b>Преимущества:</b>
• Безлимитные запросы
• Приоритетная поддержка
• Новые функции первыми

Нажмите кнопку ниже для оплаты:
    """
}
