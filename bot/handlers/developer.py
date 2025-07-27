"""
Production-ready команды для разработчиков
"""
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from database.models import Database


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


@router.message(Command("dev_stats"))
async def cmd_dev_stats(message: Message, db: Database):
    """Команда для разработчика - техническая статистика"""
    # Проверка прав разработчика
    from bot.utils.permissions import UserPermissions
    if not UserPermissions.is_developer(message.from_user.id):
        await message.answer("❌ Команда доступна только разработчикам")
        return

    logger.info(f"🔧 Разработчик {message.from_user.id} использует команду: dev_stats")

    try:
        # Получаем статистику базы данных
        total_users = await db.get_users_count()
        active_subscribers = await db.get_subscribers_count()

        # Получаем общую статистику
        total_requests = await db.get_total_requests_count()

        # Получаем статистику платежей
        from config import YOOKASSA_PROVIDER_TOKEN, YOOKASSA_CURRENCY, YOOKASSA_PROVIDER_DATA
        from services.payment_service import create_payment_service

        payment_service = create_payment_service(
            provider_token=YOOKASSA_PROVIDER_TOKEN,
            currency=YOOKASSA_CURRENCY,
            provider_data=YOOKASSA_PROVIDER_DATA,
            db=db
        )

        payment_stats = await payment_service.get_payment_statistics()

        # Режим работы
        mode = "🔴 ПРОДАКШН" if not payment_service.is_test_mode else "🧪 ТЕСТОВЫЙ"

        stats_text = f"""
🔧 <b>Техническая статистика системы</b>

👥 <b>Пользователи:</b>
• Всего: {total_users}
• Активных подписчиков: {active_subscribers}
• Общее количество запросов: {total_requests}

💰 <b>Платежи ({mode}):</b>
• Сегодня: {payment_stats.get('today', {}).get('count', 0)} платежей
• Успешных: {payment_stats.get('today', {}).get('successful', 0)}
• Сумма: {payment_stats.get('today', {}).get('amount', 0) // 100} ₽

📈 <b>За неделю:</b>
• Платежей: {payment_stats.get('week', {}).get('count', 0)}
• Успешных: {payment_stats.get('week', {}).get('successful', 0)}
• Сумма: {payment_stats.get('week', {}).get('amount', 0) // 100} ₽

🔧 <b>Система:</b>
• Версия: 2.0 Production
• Режим ЮKassa: {'LIVE' if not payment_service.is_test_mode else 'TEST'}
• Статус: Активен
        """

        await message.answer(stats_text.strip(), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка получения технической статистики: {e}")
        await message.answer(f"❌ Ошибка получения статистики: {e}")


@router.message(Command("logs"))
async def cmd_logs(message: Message):
    """Команда для разработчика - просмотр логов"""
    # Проверка прав разработчика
    from bot.utils.permissions import UserPermissions
    if not UserPermissions.is_developer(message.from_user.id):
        await message.answer("❌ Команда доступна только разработчикам")
        return

    logger.info(f"🔧 Разработчик {message.from_user.id} использует команду: logs")

    try:
        import os
        from datetime import datetime

        # Ищем файлы логов в папке logs
        log_dir = "logs"
        today_log = os.path.join(log_dir, f"findertool_{datetime.now().strftime('%Y%m%d')}.log")

        log_file = None
        if os.path.exists(today_log):
            log_file = today_log
        elif os.path.exists(log_dir):
            # Ищем любой файл логов в папке
            log_files = [f for f in os.listdir(log_dir) if f.endswith('.log') and 'findertool_' in f]
            if log_files:
                # Берем самый новый файл
                log_files.sort(reverse=True)
                log_file = os.path.join(log_dir, log_files[0])

        if not log_file or not os.path.exists(log_file):
            await message.answer("📝 Файлы логов не найдены\n\n"
                               "Логи сохраняются в папку logs/ с именем findertool_YYYYMMDD.log")
            return

        # Читаем последние 50 строк логов
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            last_lines = lines[-50:] if len(lines) > 50 else lines

        # Форматируем логи
        log_filename = os.path.basename(log_file)
        logs_text = f"📝 <b>Последние логи системы</b>\n"
        logs_text += f"📄 Файл: {log_filename}\n\n"
        logs_text += "<code>"

        for line in last_lines:
            # Обрезаем слишком длинные строки
            if len(line) > 100:
                line = line[:97] + "..."
            # Экранируем HTML символы
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            logs_text += line.strip() + "\n"

        logs_text += "</code>"

        # Telegram ограничивает сообщения до 4096 символов
        if len(logs_text) > 4000:
            logs_text = logs_text[:4000] + "\n...</code>\n\n📄 Логи обрезаны"

        await message.answer(logs_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка чтения логов: {e}")
        await message.answer(f"❌ Ошибка чтения логов: {e}")


@router.message(Command("restart"))
async def cmd_restart_info(message: Message):
    """Информация о перезапуске системы"""
    # Проверка прав разработчика
    from bot.utils.permissions import UserPermissions
    if not UserPermissions.is_developer(message.from_user.id):
        await message.answer("❌ Команда доступна только разработчикам")
        return

    logger.info(f"🔧 Разработчик {message.from_user.id} запросил информацию о перезапуске")

    try:
        await message.answer(
            "🔄 <b>Информация о перезапуске системы</b>\n\n"
            "В production режиме автоматический перезапуск отключен для безопасности.\n\n"
            "📋 <b>Для перезапуска используйте:</b>\n"
            "• Остановка: Ctrl+C в терминале\n"
            "• Запуск: python main.py\n"
            "• Или системные команды управления процессами\n\n"
            "⚠️ <b>Перед перезапуском:</b>\n"
            "• Убедитесь, что нет активных операций\n"
            "• Сохраните важные данные\n"
            "• Проверьте логи на ошибки\n\n"
            "✅ Система стабильна и не требует перезапуска",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка команды restart info: {e}")
        await message.answer(f"❌ Ошибка: {e}")
