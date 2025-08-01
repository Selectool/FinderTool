"""
Production-ready логирование для FinderTool
"""
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional


class ProductionLogger:
    """Настройка логирования для продакшн среды"""
    
    @staticmethod
    def setup_logging(
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        """
        Настроить логирование для продакшн
        
        Args:
            log_level: Уровень логирования
            log_file: Путь к файлу логов
            max_file_size: Максимальный размер файла лога
            backup_count: Количество резервных файлов
        """
        # Создаем директорию для логов если её нет
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
        
        # Настройка форматирования
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Корневой логгер
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Очищаем существующие обработчики
        root_logger.handlers.clear()
        
        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Файловый обработчик с ротацией
        if log_file:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, log_level.upper()))
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        
        # Отдельный обработчик для ошибок
        if log_file:
            error_file = log_file.replace('.log', '_errors.log')
            error_handler = logging.handlers.RotatingFileHandler(
                error_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            root_logger.addHandler(error_handler)
        
        # Настройка логгеров библиотек
        logging.getLogger('aiogram').setLevel(logging.WARNING)
        logging.getLogger('aiohttp').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        
        # Логгер для метрик
        metrics_logger = logging.getLogger('metrics')
        if log_file:
            metrics_file = log_file.replace('.log', '_metrics.log')
            metrics_handler = logging.handlers.RotatingFileHandler(
                metrics_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            metrics_handler.setLevel(logging.INFO)
            metrics_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            metrics_logger.addHandler(metrics_handler)
            metrics_logger.setLevel(logging.INFO)
            metrics_logger.propagate = False
        
        logging.info("Production logging настроен успешно")


class MetricsLogger:
    """Логгер для метрик и статистики"""
    
    def __init__(self):
        self.logger = logging.getLogger('metrics')
    
    def log_user_action(self, user_id: int, action: str, details: str = ""):
        """Логировать действие пользователя"""
        self.logger.info(f"USER_ACTION|{user_id}|{action}|{details}")
    
    def log_payment(self, user_id: int, amount: int, status: str, payment_id: str = ""):
        """Логировать платеж"""
        self.logger.info(f"PAYMENT|{user_id}|{amount}|{status}|{payment_id}")
    
    def log_search(self, user_id: int, channels_count: int, results_count: int):
        """Логировать поиск каналов"""
        self.logger.info(f"SEARCH|{user_id}|{channels_count}|{results_count}")
    
    def log_error(self, error_type: str, details: str, user_id: int = None):
        """Логировать ошибку"""
        user_part = f"|{user_id}" if user_id else ""
        self.logger.error(f"ERROR|{error_type}|{details}{user_part}")
    
    def log_performance(self, operation: str, duration: float, details: str = ""):
        """Логировать производительность"""
        self.logger.info(f"PERFORMANCE|{operation}|{duration:.3f}s|{details}")


class ErrorHandler:
    """Обработчик ошибок для продакшн"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.metrics = MetricsLogger()
    
    async def handle_user_error(self, user_id: int, error: Exception, context: str = ""):
        """Обработать ошибку пользователя"""
        error_msg = f"Ошибка для пользователя {user_id}: {str(error)}"
        if context:
            error_msg += f" (контекст: {context})"
        
        self.logger.error(error_msg, exc_info=True)
        self.metrics.log_error("USER_ERROR", str(error), user_id)
    
    async def handle_payment_error(self, user_id: int, error: Exception, payment_data: dict = None):
        """Обработать ошибку платежа"""
        error_msg = f"Ошибка платежа для пользователя {user_id}: {str(error)}"
        if payment_data:
            error_msg += f" (данные: {payment_data})"
        
        self.logger.error(error_msg, exc_info=True)
        self.metrics.log_error("PAYMENT_ERROR", str(error), user_id)
    
    async def handle_system_error(self, error: Exception, context: str = ""):
        """Обработать системную ошибку"""
        error_msg = f"Системная ошибка: {str(error)}"
        if context:
            error_msg += f" (контекст: {context})"
        
        self.logger.critical(error_msg, exc_info=True)
        self.metrics.log_error("SYSTEM_ERROR", str(error))


def setup_production_logging():
    """Настроить логирование для продакшн"""
    log_dir = "logs"
    log_file = os.path.join(log_dir, f"findertool_{datetime.now().strftime('%Y%m%d')}.log")
    
    ProductionLogger.setup_logging(
        log_level="INFO",
        log_file=log_file,
        max_file_size=10 * 1024 * 1024,  # 10MB
        backup_count=7  # Неделя логов
    )


# Глобальные экземпляры
metrics_logger = MetricsLogger()
error_handler = ErrorHandler()


def log_user_action(user_id: int, action: str, details: str = ""):
    """Удобная функция для логирования действий пользователя"""
    metrics_logger.log_user_action(user_id, action, details)


def log_payment(user_id: int, amount: int, status: str, payment_id: str = ""):
    """Удобная функция для логирования платежей"""
    metrics_logger.log_payment(user_id, amount, status, payment_id)


def log_search(user_id: int, channels_count: int, results_count: int):
    """Удобная функция для логирования поисков"""
    metrics_logger.log_search(user_id, channels_count, results_count)


async def handle_error(error: Exception, user_id: int = None, context: str = ""):
    """Удобная функция для обработки ошибок"""
    if user_id:
        await error_handler.handle_user_error(user_id, error, context)
    else:
        await error_handler.handle_system_error(error, context)
