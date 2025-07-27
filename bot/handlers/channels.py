"""
Обработчики для поиска каналов - Enterprise Edition
"""
import re
import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import StateFilter

from database.models import Database
from services.channel_finder import ChannelFinder
from bot.utils.production_logger import log_user_action, log_search, handle_error
from config import API_ID, API_HASH, SESSION_NAME, SESSION_STRING, FREE_REQUESTS_LIMIT, TEXTS

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
    """Обработчик поиска похожих каналов с production-ready обработкой ошибок"""
    user_id = message.from_user.id

    try:
        # Логируем начало поиска
        log_user_action(user_id, "SEARCH_START", message.text[:100])

        # Проверяем, может ли пользователь сделать запрос
        can_request = await db.can_make_request(user_id, FREE_REQUESTS_LIMIT)

        if not can_request:
            log_user_action(user_id, "SEARCH_BLOCKED", "No requests left")
            await message.answer(
                TEXTS["no_requests_left"].format(
                    limit=FREE_REQUESTS_LIMIT,
                    price=349  # Обновленная цена
                ),
                parse_mode="HTML"
            )
            return

        # Отправляем сообщение о начале поиска
        processing_msg = await message.answer(TEXTS["processing"])
        # Получаем ChannelFinder
        finder = await get_channel_finder()
        
        # Ищем похожие каналы
        results = await finder.find_similar_channels(message.text)
        
        # Форматируем результаты
        response_text = finder.format_results(results)
        
        # Обновляем счетчик запросов пользователя
        await db.update_user_requests(user_id)

        # Логируем результаты поиска
        channels_found = results.get('total_found', 0)
        input_channels = len(finder.extract_channel_usernames(message.text))
        log_search(user_id, input_channels, channels_found)

        # Сохраняем запрос в базу
        if results['success']:
            await db.save_request(
                user_id=user_id,
                channels_input=finder.extract_channel_usernames(message.text),
                results=results['channels']
            )
            log_user_action(user_id, "SEARCH_SUCCESS", f"Found {channels_found} channels")
        else:
            log_user_action(user_id, "SEARCH_FAILED", results.get('error', 'Unknown error'))

        # Отправляем результат
        await processing_msg.edit_text(
            response_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        # Автоматически отправляем CSV файл если есть результаты
        if results['success'] and results['total_found'] > 0:
            try:
                # Генерируем Excel-совместимый CSV
                csv_data = finder.generate_excel_compatible_csv(results)
                csv_content = csv_data.getvalue()

                # Создаем имя файла
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"telegram_channels_{timestamp}.csv"

                # Отправляем файл
                csv_file = BufferedInputFile(csv_content, filename=filename)

                from bot.utils.error_handler import safe_send_document

                success = await safe_send_document(
                    bot=message.bot,
                    user_id=user_id,
                    document=csv_file,
                    db=db,
                    caption=f"📊 <b>Полный список найденных каналов</b>\n\n"
                           f"📈 Всего каналов: {results['total_found']}\n"
                           f"👥 Минимум подписчиков: {results.get('min_subscribers_filter', 1000):,}\n"
                           f"📅 Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                           f"💡 CSV содержит: название, ссылку и количество подписчиков",
                    parse_mode="HTML"
                )

                if success:
                    logger.info(f"✅ CSV файл автоматически отправлен пользователю {user_id}")
                else:
                    logger.warning(f"⚠️ Не удалось отправить CSV файл пользователю {user_id}")

            except Exception as csv_error:
                logger.error(f"Ошибка при автоматической отправке CSV: {csv_error}")
                # Если ошибка с CSV, не прерываем основной процесс
        
    except Exception as e:
        # Production-ready обработка ошибок
        await handle_error(e, user_id, "channel_search")
        log_user_action(user_id, "SEARCH_ERROR", str(e))

        try:
            await processing_msg.edit_text(TEXTS["error"])
        except Exception as edit_error:
            # Если не можем отредактировать сообщение, отправляем новое
            await message.answer(TEXTS["error"])
            logger.error(f"Не удалось отредактировать сообщение: {edit_error}")





@router.message(F.text & ~F.text.startswith('/'))
async def handle_other_messages(message: Message):
    """Обработчик остальных текстовых сообщений (кроме команд)"""
    await message.answer(
        "🤖 Отправьте ссылку на канал или несколько ссылок для поиска похожих каналов.\n\n"
        "Поддерживаемые форматы:\n"
        "• https://t.me/channel_name\n"
        "• @channel_name\n"
        "• t.me/channel_name\n\n"
        "Используйте /help для получения подробной справки."
    )
