"""
Production Logger для Telegram Channel Finder Bot
Система логирования для production окружения
"""
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_production_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Настройка production логирования
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        log_file: Путь к файлу логов (опционально)
        max_bytes: Максимальный размер файла лога
        backup_count: Количество backup файлов
    
    Returns:
        Настроенный logger
    """
    # Создаем директорию для логов если её нет
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Определяем файл лога
    if not log_file:
        log_file = log_dir / f"findertool_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Настройка форматирования
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Настройка root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем существующие handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler с ротацией
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Не удалось настроить файловое логирование: {e}")
    
    # Настройка внешних библиотек
    _configure_external_loggers(log_level)
    
    return root_logger


def _configure_external_loggers(log_level: str):
    """Настройка логирования для внешних библиотек"""
    
    # Уровни для внешних библиотек (менее подробные)
    external_level = logging.WARNING if log_level == "DEBUG" else logging.ERROR
    
    external_loggers = [
        'asyncio',
        'aiogram',
        'aiohttp',
        'urllib3',
        'asyncpg',
        'uvicorn.access',
        'uvicorn.error',
        'fastapi',
        'starlette',
        'httpx',
        'telethon'
    ]
    
    for logger_name in external_loggers:
        logging.getLogger(logger_name).setLevel(external_level)
    
    # Специальные настройки для некоторых библиотек
    logging.getLogger('uvicorn').setLevel(logging.INFO)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)


def log_user_action(user_id: int, action: str, details: str = ""):
    """Логировать действие пользователя"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_message = f"[{timestamp}] USER_ACTION: User {user_id} - {action}"
        if details:
            log_message += f" | Details: {details}"
        
        logger.info(log_message)
        
    except Exception as e:
        logger.error(f"Ошибка логирования действия пользователя: {e}")


def log_search(user_id: int, input_channels: int, found_channels: int):
    """Логировать результаты поиска каналов"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_message = f"[{timestamp}] SEARCH_RESULT: User {user_id} - Input: {input_channels} channels, Found: {found_channels} channels"
        
        logger.info(log_message)
        
    except Exception as e:
        logger.error(f"Ошибка логирования поиска: {e}")


def log_payment(user_id: int, action: str, amount: float = None, payment_id: str = None, details: str = ""):
    """Логировать действия с платежами"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_message = f"[{timestamp}] PAYMENT: User {user_id} - {action}"
        
        if amount is not None:
            log_message += f" | Amount: {amount}₽"
        
        if payment_id:
            log_message += f" | Payment ID: {payment_id}"
        
        if details:
            log_message += f" | Details: {details}"
        
        logger.info(log_message)
        
    except Exception as e:
        logger.error(f"Ошибка логирования платежа: {e}")


async def handle_error(error: Exception, user_id: int = None, context: str = ""):
    """Обработка и логирование ошибок"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        error_message = f"[{timestamp}] ERROR"
        
        if user_id:
            error_message += f" | User: {user_id}"
        
        if context:
            error_message += f" | Context: {context}"
        
        error_message += f" | Error: {type(error).__name__}: {str(error)}"
        
        logger.error(error_message)
        
        # В production можно добавить отправку уведомлений администраторам
        if os.getenv("ENVIRONMENT") == "production":
            await _notify_admins_about_error(error, user_id, context)
        
    except Exception as e:
        logger.critical(f"Критическая ошибка в обработчике ошибок: {e}")


async def _notify_admins_about_error(error: Exception, user_id: int = None, context: str = ""):
    """Уведомление администраторов о критических ошибках"""
    try:
        # Здесь можно добавить отправку уведомлений в Telegram или email
        # Пока просто логируем
        logger.critical(f"ADMIN_NOTIFICATION: Critical error occurred - {type(error).__name__}: {str(error)}")
        
    except Exception as e:
        logger.critical(f"Ошибка отправки уведомления администраторам: {e}")


def log_admin_action(admin_id: int, action: str, target: str = "", details: str = ""):
    """Логировать действия администраторов"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_message = f"[{timestamp}] ADMIN_ACTION: Admin {admin_id} - {action}"
        
        if target:
            log_message += f" | Target: {target}"
        
        if details:
            log_message += f" | Details: {details}"
        
        logger.warning(log_message)  # WARNING уровень для админских действий
        
    except Exception as e:
        logger.error(f"Ошибка логирования действия администратора: {e}")


def log_system_event(event: str, details: Dict[str, Any] = None):
    """Логировать системные события"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_message = f"[{timestamp}] SYSTEM_EVENT: {event}"
        
        if details:
            details_str = ", ".join([f"{k}: {v}" for k, v in details.items()])
            log_message += f" | {details_str}"
        
        logger.info(log_message)
        
    except Exception as e:
        logger.error(f"Ошибка логирования системного события: {e}")


def get_logger(name: str) -> logging.Logger:
    """Получение logger с указанным именем"""
    return logging.getLogger(name)


# Инициализация при импорте модуля
if not logging.getLogger().handlers:
    setup_production_logging()
