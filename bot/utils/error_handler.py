"""
Утилиты для обработки ошибок бота
"""
import logging
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from database.universal_database import UniversalDatabase

logger = logging.getLogger(__name__)


async def handle_send_message_error(error: Exception, user_id: int, db: UniversalDatabase) -> bool:
    """
    Обработка ошибок при отправке сообщений пользователям
    
    Args:
        error: Исключение, возникшее при отправке
        user_id: ID пользователя
        db: Экземпляр базы данных
        
    Returns:
        bool: True если ошибка была обработана, False если нет
    """
    
    if isinstance(error, TelegramForbiddenError):
        # Пользователь заблокировал бота
        if "bot was blocked by the user" in str(error).lower():
            logger.info(f"Пользователь {user_id} заблокировал бота")
            await db.mark_user_bot_blocked(user_id)
            return True
            
        # Пользователь удалил аккаунт или деактивировал
        elif "user is deactivated" in str(error).lower():
            logger.info(f"Пользователь {user_id} деактивировал аккаунт")
            await db.mark_user_bot_blocked(user_id)
            return True
            
    elif isinstance(error, TelegramBadRequest):
        # Чат не найден (пользователь удалил диалог)
        if "chat not found" in str(error).lower():
            logger.info(f"Чат с пользователем {user_id} не найден")
            await db.mark_user_bot_blocked(user_id)
            return True
            
    # Логируем необработанные ошибки
    logger.error(f"Необработанная ошибка отправки сообщения пользователю {user_id}: {error}")
    return False


async def safe_send_message(bot, user_id: int, text: str, db: UniversalDatabase, **kwargs) -> bool:
    """
    Безопасная отправка сообщения с автоматической обработкой ошибок блокировки
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        text: Текст сообщения
        db: Экземпляр базы данных
        **kwargs: Дополнительные параметры для send_message
        
    Returns:
        bool: True если сообщение отправлено успешно, False если нет
    """
    try:
        await bot.send_message(chat_id=user_id, text=text, **kwargs)
        return True
        
    except Exception as e:
        await handle_send_message_error(e, user_id, db)
        return False


async def safe_send_document(bot, user_id: int, document, db: UniversalDatabase, **kwargs) -> bool:
    """
    Безопасная отправка документа с автоматической обработкой ошибок блокировки
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        document: Документ для отправки
        db: Экземпляр базы данных
        **kwargs: Дополнительные параметры для send_document
        
    Returns:
        bool: True если документ отправлен успешно, False если нет
    """
    try:
        await bot.send_document(chat_id=user_id, document=document, **kwargs)
        return True
        
    except Exception as e:
        await handle_send_message_error(e, user_id, db)
        return False


async def safe_answer_message(message, text: str, db: UniversalDatabase, **kwargs) -> bool:
    """
    Безопасный ответ на сообщение с автоматической обработкой ошибок блокировки
    
    Args:
        message: Объект сообщения
        text: Текст ответа
        db: Экземпляр базы данных
        **kwargs: Дополнительные параметры для answer
        
    Returns:
        bool: True если ответ отправлен успешно, False если нет
    """
    try:
        await message.answer(text, **kwargs)
        return True
        
    except Exception as e:
        await handle_send_message_error(e, message.from_user.id, db)
        return False


async def safe_edit_message(message, text: str, db: UniversalDatabase, **kwargs) -> bool:
    """
    Безопасное редактирование сообщения с автоматической обработкой ошибок блокировки
    
    Args:
        message: Объект сообщения
        text: Новый текст сообщения
        db: Экземпляр базы данных
        **kwargs: Дополнительные параметры для edit_text
        
    Returns:
        bool: True если сообщение отредактировано успешно, False если нет
    """
    try:
        await message.edit_text(text, **kwargs)
        return True
        
    except Exception as e:
        await handle_send_message_error(e, message.from_user.id if hasattr(message, 'from_user') else 0, db)
        return False
