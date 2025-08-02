#!/usr/bin/env python3
"""
Запуск админ-панели отдельно от основного бота
"""

import asyncio
import logging
import os
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

async def main():
    """Запуск админ-панели"""
    logger.info("🚀 Запуск админ-панели...")
    
    try:
        # Импортируем и запускаем админ-панель
        from run_admin import main as admin_main
        await admin_main()
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта админ-панели: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска админ-панели: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Админ-панель остановлена пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
