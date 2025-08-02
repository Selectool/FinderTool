"""
Production Logging Configuration
Настройка логирования для production окружения
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional

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
    
    # Получаем уровень логирования из переменных окружения
    log_level = os.getenv('LOG_LEVEL', log_level).upper()
    log_file = log_file or os.getenv('LOG_FILE')
    
    # Создаем основной logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Очищаем существующие handlers
    logger.handlers.clear()
    
    # Формат логов для production
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (всегда включен)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    logger.addHandler(console_handler)
    
    # File handler (если указан файл)
    if log_file:
        try:
            # Создаем директорию для логов если не существует
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            # Rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(getattr(logging, log_level, logging.INFO))
            logger.addHandler(file_handler)
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось настроить файловое логирование: {e}")
    
    # Настройка логирования для внешних библиотек
    _configure_external_loggers(log_level)
    
    # Логируем успешную настройку
    logger.info("✅ Production логирование настроено")
    logger.info(f"📊 Уровень логирования: {log_level}")
    if log_file:
        logger.info(f"📁 Файл логов: {log_file}")
    
    return logger

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

def get_logger(name: str) -> logging.Logger:
    """Получение logger с указанным именем"""
    return logging.getLogger(name)

def log_startup_info():
    """Логирование информации о запуске"""
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 50)
    logger.info("🚀 TELEGRAM CHANNEL FINDER BOT")
    logger.info("=" * 50)
    logger.info(f"🕐 Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🐍 Python версия: {sys.version}")
    logger.info(f"🌍 Окружение: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"🗄️ База данных: {os.getenv('DATABASE_TYPE', 'sqlite')}")
    logger.info("=" * 50)

def log_shutdown_info():
    """Логирование информации о завершении"""
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 50)
    logger.info("🛑 ЗАВЕРШЕНИЕ РАБОТЫ ПРИЛОЖЕНИЯ")
    logger.info(f"🕐 Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

class ProductionLogFilter(logging.Filter):
    """Фильтр для production логов"""
    
    def __init__(self, environment: str = "production"):
        super().__init__()
        self.environment = environment
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Фильтрация записей лога"""
        
        # В production скрываем DEBUG сообщения от внешних библиотек
        if self.environment == "production":
            if record.levelno < logging.INFO and not record.name.startswith('bot'):
                return False
        
        # Скрываем чувствительную информацию
        if hasattr(record, 'msg'):
            sensitive_patterns = ['password', 'token', 'secret', 'key']
            msg_lower = str(record.msg).lower()
            
            for pattern in sensitive_patterns:
                if pattern in msg_lower:
                    record.msg = str(record.msg).replace(
                        record.msg, 
                        "[SENSITIVE DATA HIDDEN]"
                    )
        
        return True

# Настройка по умолчанию при импорте модуля
if not logging.getLogger().handlers:
    setup_production_logging()
