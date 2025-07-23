"""
Production-ready команды для разработчиков
"""
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command


from services.channel_finder import ChannelFinder

logger = logging.getLogger(__name__)
router = Router()

# Глобальный экземпляр для команд разработчика
_channel_finder = None


async def get_channel_finder():
    """Получить экземпляр ChannelFinder для команд разработчика"""
    global _channel_finder
    if not _channel_finder:
        from config import API_ID, API_HASH, SESSION_NAME, SESSION_STRING
        _channel_finder = ChannelFinder(API_ID, API_HASH, SESSION_NAME, SESSION_STRING)
    return _channel_finder


@router.message(Command("dev_metrics"))
async def cmd_dev_metrics(message: Message):
    """Команда для разработчика - просмотр метрик производительности"""
    # Проверка прав разработчика
    from bot.utils.permissions import UserPermissions
    if not UserPermissions.is_developer(message.from_user.id):
        await message.answer("❌ Команда доступна только разработчикам")
        return

    logger.info(f"🔧 Разработчик {message.from_user.id} использует команду: dev_metrics")

    try:
        finder = await get_channel_finder()
        metrics = finder.get_performance_metrics()
        
        metrics_text = f"""
🔧 <b>Метрики производительности ChannelFinder</b>

📊 <b>Статистика поиска:</b>
• Всего поисков: {metrics['total_searches']}
• Успешных: {metrics['successful_searches']}
• Неудачных: {metrics['failed_searches']}
• Успешность: {metrics['success_rate']}%

📈 <b>Качество результатов:</b>
• Среднее кол-во каналов: {metrics['avg_results_count']}
• Размер кэша: {metrics['cache_size']} записей

⚡ <b>Производительность:</b>
• API вызовов: {metrics['api_calls_count']}
• Попаданий в кэш: {metrics['cache_hits']}
• Эффективность кэша: {metrics['cache_hit_rate']}%

🛠️ <b>Команды разработчика:</b>
/dev_metrics - Показать метрики
/dev_clear_cache - Очистить кэш
/dev_reset_metrics - Сбросить метрики
/dev_status - Статус системы
        """
        
        await message.answer(metrics_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка получения метрик: {e}")
        await message.answer(f"❌ Ошибка получения метрик: {e}")


@router.message(Command("dev_clear_cache"))
async def cmd_dev_clear_cache(message: Message):
    """Команда для разработчика - очистка кэша"""
    # Проверка прав разработчика
    from bot.utils.permissions import UserPermissions
    if not UserPermissions.is_developer(message.from_user.id):
        await message.answer("❌ Команда доступна только разработчикам")
        return

    logger.info(f"🔧 Разработчик {message.from_user.id} использует команду: dev_clear_cache")

    try:
        finder = await get_channel_finder()
        cache_size_before = len(finder.channel_cache)
        finder.clear_cache()
        await message.answer(f"✅ Кэш очищен успешно\n📊 Удалено записей: {cache_size_before}")
    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {e}")
        await message.answer(f"❌ Ошибка очистки кэша: {e}")


@router.message(Command("dev_reset_metrics"))
async def cmd_dev_reset_metrics(message: Message):
    """Команда для разработчика - сброс метрик"""
    # Проверка прав разработчика
    from bot.utils.permissions import UserPermissions
    if not UserPermissions.is_developer(message.from_user.id):
        await message.answer("❌ Команда доступна только разработчикам")
        return

    logger.info(f"🔧 Разработчик {message.from_user.id} использует команду: dev_reset_metrics")

    try:
        finder = await get_channel_finder()
        finder.reset_metrics()
        await message.answer("✅ Метрики сброшены успешно")
    except Exception as e:
        logger.error(f"Ошибка сброса метрик: {e}")
        await message.answer(f"❌ Ошибка сброса метрик: {e}")


@router.message(Command("dev_status"))
async def cmd_dev_status(message: Message):
    """Команда для разработчика - статус системы"""
    # Проверка прав разработчика
    from bot.utils.permissions import UserPermissions
    if not UserPermissions.is_developer(message.from_user.id):
        await message.answer("❌ Команда доступна только разработчикам")
        return

    logger.info(f"🔧 Разработчик {message.from_user.id} использует команду: dev_status")

    try:
        finder = await get_channel_finder()
        
        # Проверяем статус клиента
        client_status = "🟢 Подключен" if finder.client and finder.client.is_connected() else "🔴 Отключен"
        
        status_text = f"""
🔧 <b>Статус системы ChannelFinder</b>

📡 <b>Telegram клиент:</b> {client_status}
🗄️ <b>Размер кэша:</b> {len(finder.channel_cache)} записей
📊 <b>Всего поисков:</b> {finder.search_metrics['total_searches']}
⚡ <b>Успешность:</b> {finder.search_metrics.get('success_rate', 0)}%

🛠️ <b>Версия:</b> Enterprise v2.0
🚀 <b>Статус:</b> Production Ready
        """
        
        await message.answer(status_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}")
        await message.answer(f"❌ Ошибка получения статуса: {e}")
