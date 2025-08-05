"""
Регистрация всех обработчиков для Telegram бота
Production-ready система с поддержкой admin access
"""

import logging
from aiogram import Dispatcher

logger = logging.getLogger(__name__)

def register_handlers(dp: Dispatcher):
    """
    Регистрация всех обработчиков бота
    Порядок важен для корректной работы FSM состояний
    """
    try:
        logger.info("🔧 Регистрация обработчиков бота...")
        
        # Импортируем все роутеры
        from . import (
            admin_access,  # Secure admin access - должен быть первым
            admin,         # Админ команды
            basic,         # Базовые команды (/start, /help)
            subscription,  # Подписка и платежи
            channels,      # Поиск каналов
            reply_menu,    # Reply клавиатура
            developer,     # Команды разработчика
            role_management,  # Управление ролями
            feedback,      # Обратная связь
            payment_stats  # Статистика платежей
        )
        
        # Регистрируем роутеры в правильном порядке
        routers = [
            admin_access.router,    # Secure admin access - ПЕРВЫЙ
            admin.router,          # Админ команды - второй для FSM
            reply_menu.router,     # Reply клавиатура
            basic.router,          # Базовые команды
            subscription.router,   # Подписка и платежи
            channels.router,       # Поиск каналов
            developer.router,      # Команды разработчика
            role_management.router, # Управление ролями
            feedback.router,       # Обратная связь
            payment_stats.router   # Статистика платежей
        ]
        
        # Подключаем все роутеры
        for i, router in enumerate(routers):
            dp.include_router(router)
            logger.info(f"✅ Роутер {i+1}/{len(routers)} подключен: {router}")
        
        logger.info("✅ Все обработчики успешно зарегистрированы")
        
        # Запускаем фоновые задачи
        _start_background_tasks()
        
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта обработчиков: {e}")
        logger.info("🔄 Пытаемся зарегистрировать доступные обработчики...")
        
        # Fallback - регистрируем только доступные обработчики
        _register_available_handlers(dp)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка регистрации обработчиков: {e}")
        raise

def _register_available_handlers(dp: Dispatcher):
    """Fallback регистрация только доступных обработчиков"""
    available_handlers = []
    
    # Список обработчиков для проверки
    handler_modules = [
        'admin_access', 'admin', 'basic', 'subscription', 
        'channels', 'reply_menu', 'developer', 'role_management',
        'feedback', 'payment_stats'
    ]
    
    for module_name in handler_modules:
        try:
            module = __import__(f'bot.handlers.{module_name}', fromlist=['router'])
            if hasattr(module, 'router'):
                dp.include_router(module.router)
                available_handlers.append(module_name)
                logger.info(f"✅ Обработчик {module_name} подключен")
        except ImportError as e:
            logger.warning(f"⚠️ Обработчик {module_name} недоступен: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения {module_name}: {e}")
    
    logger.info(f"✅ Подключено {len(available_handlers)} обработчиков: {', '.join(available_handlers)}")

def _start_background_tasks():
    """Запуск фоновых задач"""
    try:
        import asyncio
        
        # Запускаем задачу очистки токенов admin access
        try:
            from .admin_access import cleanup_expired_tokens_task
            asyncio.create_task(cleanup_expired_tokens_task())
            logger.info("✅ Фоновая задача очистки токенов запущена")
        except ImportError:
            logger.warning("⚠️ Модуль admin_access недоступен для фоновых задач")
        
        # Здесь можно добавить другие фоновые задачи
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска фоновых задач: {e}")

# Экспорт основной функции
__all__ = ['register_handlers']
