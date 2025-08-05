"""
FastAPI Dependencies для админ-панели
"""
import logging
from typing import Generator
from fastapi import Depends, HTTPException, status
from database.universal_database import UniversalDatabase

logger = logging.getLogger(__name__)

# Глобальная переменная для кэширования подключения к БД
_db_instance = None


def get_db() -> Generator[UniversalDatabase, None, None]:
    """
    Dependency для получения подключения к базе данных
    """
    global _db_instance
    
    try:
        # Создаем экземпляр БД если его нет
        if _db_instance is None:
            from config import DATABASE_URL
            _db_instance = UniversalDatabase(DATABASE_URL)
            logger.info("Создан новый экземпляр базы данных")
        
        yield _db_instance
        
    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен"
        )


async def get_db_async() -> UniversalDatabase:
    """
    Асинхронная версия dependency для получения БД
    """
    global _db_instance
    
    try:
        if _db_instance is None:
            from config import DATABASE_URL
            _db_instance = UniversalDatabase(DATABASE_URL)
            logger.info("Создан новый экземпляр базы данных (async)")
        
        return _db_instance
        
    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных (async): {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен"
        )


def reset_db_connection():
    """
    Сброс подключения к базе данных (для тестов или переподключения)
    """
    global _db_instance
    _db_instance = None
    logger.info("Подключение к базе данных сброшено")


def get_current_db_instance() -> UniversalDatabase:
    """
    Получить текущий экземпляр базы данных без dependency injection
    """
    global _db_instance
    
    if _db_instance is None:
        from config import DATABASE_URL
        _db_instance = UniversalDatabase(DATABASE_URL)
        logger.info("Создан новый экземпляр базы данных (direct)")
    
    return _db_instance
