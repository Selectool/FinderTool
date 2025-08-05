"""
Инициализация сервисов
"""
from .statistics_service import StatisticsService

# Глобальный экземпляр сервиса статистики
_statistics_service = None


def get_statistics_service():
    """Получить глобальный экземпляр сервиса статистики"""
    global _statistics_service
    if _statistics_service is None:
        raise RuntimeError("Сервис статистики не инициализирован. Вызовите init_statistics_service() сначала.")
    return _statistics_service


def init_statistics_service(db, cache_ttl: int = 300):
    """Инициализировать глобальный сервис статистики"""
    global _statistics_service
    _statistics_service = StatisticsService(db, cache_ttl)
    return _statistics_service


def is_statistics_service_initialized() -> bool:
    """Проверить, инициализирован ли сервис статистики"""
    return _statistics_service is not None
