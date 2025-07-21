"""
Обработчики для поиска каналов
"""
import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter

from database.models import Database
from services.channel_finder import ChannelFinder
from config import API_ID, API_HASH, SESSION_NAME, SESSION_STRING, FREE_REQUESTS_LIMIT, TEXTS
import logging

logger = logging.getLogger(__name__)
router = Router()

# Глобальный экземпляр ChannelFinder
channel_finder = None


async def get_channel_finder():
    """Получить экземпляр ChannelFinder"""
    global channel_finder
    if not channel_finder:
        # Приоритет: строковая сессия > файловая сессия
        channel_finder = ChannelFinder(
            API_ID,
            API_HASH,
            session_string=SESSION_STRING if SESSION_STRING else None,
            session_name=SESSION_NAME
        )
    return channel_finder


def has_channel_links(text: str) -> bool:
    """Проверить, содержит ли текст ссылки на каналы"""
    patterns = [
        r'https?://t\.me/[a-zA-Z0-9_]+',
        r't\.me/[a-zA-Z0-9_]+',
        r'@[a-zA-Z0-9_]+',
    ]
    
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False


@router.message(F.text & F.func(lambda message: has_channel_links(message.text)))
async def handle_channel_search(message: Message, db: Database):
    """Обработчик поиска похожих каналов"""
    user_id = message.from_user.id
    
    # Проверяем, может ли пользователь сделать запрос
    can_request = await db.can_make_request(user_id, FREE_REQUESTS_LIMIT)
    
    if not can_request:
        await message.answer(
            TEXTS["no_requests_left"].format(
                limit=FREE_REQUESTS_LIMIT,
                price=500  # Из config.py
            ),
            parse_mode="HTML"
        )
        return
    
    # Отправляем сообщение о начале поиска
    processing_msg = await message.answer(TEXTS["processing"])
    
    try:
        # Получаем ChannelFinder
        finder = await get_channel_finder()
        
        # Ищем похожие каналы
        results = await finder.find_similar_channels(message.text)
        
        # Форматируем результаты
        response_text = finder.format_results(results)
        
        # Обновляем счетчик запросов пользователя
        await db.update_user_requests(user_id)
        
        # Сохраняем запрос в базу
        if results['success']:
            await db.save_request(
                user_id=user_id,
                channels_input=finder.extract_channel_usernames(message.text),
                results=results['channels']
            )
        
        # Отправляем результат
        await processing_msg.edit_text(
            response_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Ошибка при поиске каналов: {e}")
        await processing_msg.edit_text(TEXTS["error"])


@router.message(F.text)
async def handle_other_messages(message: Message):
    """Обработчик остальных текстовых сообщений"""
    await message.answer(
        "🤖 Отправьте ссылку на канал или несколько ссылок для поиска похожих каналов.\n\n"
        "Поддерживаемые форматы:\n"
        "• https://t.me/channel_name\n"
        "• @channel_name\n"
        "• t.me/channel_name\n\n"
        "Используйте /help для получения подробной справки."
    )
