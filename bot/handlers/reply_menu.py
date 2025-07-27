"""
Обработчики Reply клавиатуры для FinderTool
Production-ready реализация с поддержкой ролей
"""
import logging
from aiogram import Router, F
from aiogram.types import Message

from database.models import Database
from bot.keyboards.reply import (
    ReplyButtons, get_main_menu_keyboard, get_admin_menu_keyboard,
    get_subscription_menu_keyboard, is_reply_button
)
from bot.keyboards.inline import get_main_menu, get_subscription_keyboard, get_back_keyboard
from services.payment_service import create_payment_service
from config import (TEXTS, SUBSCRIPTION_PRICE, FREE_REQUESTS_LIMIT,
                   YOOKASSA_PROVIDER_TOKEN, YOOKASSA_CURRENCY, YOOKASSA_PROVIDER_DATA)
from bot.utils.roles import TelegramUserPermissions

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == ReplyButtons.MAIN_MENU)
@router.message(F.text == ReplyButtons.MENU_SHORT)
async def handle_main_menu(message: Message, db: Database):
    """Обработчик кнопки Главное меню"""
    try:
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        user_role = user.get('role', 'user') if user else 'user'
        
        # Отправляем главное меню с Reply клавиатурой
        await message.answer(
            TEXTS["start"].format(price=SUBSCRIPTION_PRICE),
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(user_role)
        )
        
        logger.info(f"Пользователь {user_id} открыл главное меню")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке главного меню для {message.from_user.id}: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=get_main_menu_keyboard()
        )


@router.message(F.text == ReplyButtons.PROFILE)
@router.message(F.text == ReplyButtons.PROFILE_SHORT)
async def handle_profile(message: Message, db: Database):
    """Обработчик кнопки Мой профиль"""
    try:
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        
        if not user:
            await db.create_user(
                user_id, 
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
            user = await db.get_user(user_id)
        
        # Проверяем подписку
        is_subscribed = await db.check_subscription(user_id)
        subscription_text = "✅ Активна" if is_subscribed else "❌ Неактивна"
        
        # Проверяем роль
        user_role = user.get('role', 'user')
        role_emoji = {
            'developer': '🔧',
            'senior_admin': '👑',
            'admin': '🛡️',
            'user': '👤'
        }
        role_names = {
            'developer': 'Разработчик',
            'senior_admin': 'Старший админ',
            'admin': 'Администратор',
            'user': 'Пользователь'
        }
        
        profile_text = f"""
👤 <b>Ваш профиль</b>

🆔 ID: <code>{user_id}</code>
👤 Имя: {user.get('first_name', 'Не указано')}
📝 Username: @{user.get('username', 'не указан')}
{role_emoji.get(user_role, '👤')} Роль: {role_names.get(user_role, 'Пользователь')}

📊 <b>Статистика использования:</b>
🔍 Запросов использовано: {user.get('requests_used', 0)} из {FREE_REQUESTS_LIMIT} бесплатных
💎 Подписка: {subscription_text}

📅 Дата регистрации: {user.get('created_at', 'Неизвестно')[:10] if user.get('created_at') else 'Неизвестно'}
        """
        
        if is_subscribed and user.get('subscription_end'):
            profile_text += f"\n⏰ Подписка до: {user['subscription_end'][:10]}"
        
        await message.answer(
            profile_text.strip(),
            parse_mode="HTML"
        )
        
        logger.info(f"Пользователь {user_id} просмотрел профиль")
        
    except Exception as e:
        logger.error(f"Ошибка при показе профиля для {message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при загрузке профиля.")


@router.message(F.text == ReplyButtons.SUBSCRIPTION)
@router.message(F.text == ReplyButtons.SUBSCRIPTION_SHORT)
async def handle_subscription(message: Message, db: Database):
    """Обработчик кнопки Подписка"""
    try:
        user_id = message.from_user.id
        is_subscribed = await db.check_subscription(user_id)
        
        if is_subscribed:
            user = await db.get_user(user_id)
            subscription_end = user.get('subscription_end', 'Неизвестно')[:10] if user.get('subscription_end') else 'Неизвестно'
            
            await message.answer(
                f"💎 <b>У вас есть активная подписка!</b>\n\n"
                f"⏰ Действует до: {subscription_end}\n"
                f"🔍 Безлимитные запросы активны\n\n"
                f"Используйте /profile для подробной информации.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                TEXTS["subscription_info"].format(price=SUBSCRIPTION_PRICE),
                parse_mode="HTML",
                reply_markup=get_subscription_keyboard()
            )
        
        logger.info(f"Пользователь {user_id} открыл раздел подписки")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке подписки для {message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при загрузке информации о подписке.")


@router.message(F.text == ReplyButtons.HELP)
@router.message(F.text == ReplyButtons.HELP_SHORT)
async def handle_help(message: Message):
    """Обработчик кнопки Помощь"""
    try:
        await message.answer(
            TEXTS["help"],
            parse_mode="HTML"
        )
        
        logger.info(f"Пользователь {message.from_user.id} открыл справку")
        
    except Exception as e:
        logger.error(f"Ошибка при показе справки для {message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при загрузке справки.")


@router.message(F.text == ReplyButtons.ADMIN_PANEL)
@router.message(F.text == ReplyButtons.ADMIN_SHORT)
async def handle_admin_panel(message: Message, db: Database):
    """Обработчик кнопки Админ панель"""
    try:
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        user_role = user.get('role', 'user') if user else 'user'
        
        # Проверяем права доступа
        if not TelegramUserPermissions.has_admin_access(user_id, user_role):
            await message.answer(
                "❌ У вас нет прав для доступа к админ-панели.",
                parse_mode="HTML"
            )
            return
        
        # Получаем статистику для админов
        stats = await db.get_stats()
        
        admin_text = f"""
⚙️ <b>Админ панель FinderTool</b>

📊 <b>Статистика:</b>
👥 Всего пользователей: {stats.get('total_users', 0)}
💎 Активных подписчиков: {stats.get('active_subscribers', 0)}
🔍 Запросов сегодня: {stats.get('requests_today', 0)}

🛡️ Ваша роль: {user_role}

Используйте команды:
• /admin - Полная админ-панель
• /payment_stats - Статистика платежей
• /stats - Детальная статистика
        """
        
        await message.answer(
            admin_text.strip(),
            parse_mode="HTML",
            reply_markup=get_admin_menu_keyboard()
        )
        
        logger.info(f"Админ {user_id} ({user_role}) открыл админ-панель")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке админ-панели для {message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при загрузке админ-панели.")


@router.message(F.text == ReplyButtons.DEV_PANEL)
async def handle_dev_panel(message: Message, db: Database):
    """Обработчик кнопки Dev панель (только для разработчиков)"""
    try:
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        user_role = user.get('role', 'user') if user else 'user'
        
        # Проверяем права разработчика
        if user_role != 'developer':
            await message.answer("❌ Доступ только для разработчиков.")
            return
        
        # Получаем режим ЮKassa из конфигурации
        from config import YOOKASSA_MODE, YOOKASSA_PROVIDER_TOKEN
        yookassa_mode = YOOKASSA_MODE
        is_live_mode = ":LIVE:" in YOOKASSA_PROVIDER_TOKEN

        dev_text = f"""
🔧 <b>Панель разработчика</b>

🚀 <b>Системная информация:</b>
• Режим ЮKassa: {'LIVE' if is_live_mode else 'TEST'}
• Версия бота: 2.0 Production
• Статус: Активен

🛠️ <b>Доступные команды:</b>
• /dev_stats - Техническая статистика
• /logs - Просмотр логов системы
• /restart - Информация о перезапуске

💡 Все команды безопасны для использования
        """
        
        await message.answer(
            dev_text.strip(),
            parse_mode="HTML"
        )
        
        logger.info(f"Разработчик {user_id} открыл dev-панель")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке dev-панели для {message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при загрузке dev-панели.")


@router.message(F.text == ReplyButtons.STATISTICS)
async def handle_statistics(message: Message, db: Database):
    """Обработчик кнопки Статистика"""
    try:
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        user_role = user.get('role', 'user') if user else 'user'

        # Проверяем права доступа
        if not TelegramUserPermissions.has_admin_access(user_id, user_role):
            await message.answer("❌ У вас нет прав для доступа к статистике.")
            return

        # Получаем статистику
        stats = await db.get_stats()

        stats_text = f"""
📊 <b>Статистика FinderTool</b>

👥 Всего пользователей: {stats['total_users']}
💎 Активных подписчиков: {stats['active_subscribers']}
🔍 Запросов сегодня: {stats['requests_today']}

📈 Конверсия в подписку: {(stats['active_subscribers'] / max(stats['total_users'], 1) * 100):.1f}%

🛡️ Ваша роль: {user_role}
        """

        await message.answer(
            stats_text.strip(),
            parse_mode="HTML"
        )

        logger.info(f"Админ {user_id} ({user_role}) просмотрел статистику")

    except Exception as e:
        logger.error(f"Ошибка при показе статистики для {message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при загрузке статистики.")


@router.message(F.text == ReplyButtons.PAYMENTS)
async def handle_payments(message: Message, db: Database):
    """Обработчик кнопки Платежи"""
    try:
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        user_role = user.get('role', 'user') if user else 'user'

        # Проверяем права доступа
        if not TelegramUserPermissions.has_admin_access(user_id, user_role):
            await message.answer("❌ У вас нет прав для доступа к статистике платежей.")
            return

        # Создаем сервис платежей
        payment_service = create_payment_service(
            provider_token=YOOKASSA_PROVIDER_TOKEN,
            currency=YOOKASSA_CURRENCY,
            provider_data=YOOKASSA_PROVIDER_DATA,
            db=db
        )

        # Получаем статистику
        stats = await payment_service.get_payment_statistics()

        if not stats:
            await message.answer("❌ Не удалось получить статистику платежей.")
            return

        # Форматируем статистику
        mode = "🧪 ТЕСТОВЫЙ" if payment_service.is_test_mode else "🔴 ПРОДАКШН"

        stats_text = f"""
💳 <b>Статистика платежей ЮKassa</b>
{mode} режим

📅 <b>За сегодня:</b>
• Платежей: {stats.get('today', {}).get('count', 0)}
• Успешных: {stats.get('today', {}).get('successful', 0)}
• Сумма: {stats.get('today', {}).get('amount', 0) // 100} ₽

📈 <b>За неделю:</b>
• Платежей: {stats.get('week', {}).get('count', 0)}
• Успешных: {stats.get('week', {}).get('successful', 0)}
• Сумма: {stats.get('week', {}).get('amount', 0) // 100} ₽

📊 <b>Всего:</b>
• Платежей: {stats.get('total', {}).get('count', 0)}
• Успешных: {stats.get('total', {}).get('successful', 0)}
• Сумма: {stats.get('total', {}).get('amount', 0) // 100} ₽

🛡️ Ваша роль: {user_role}
        """

        await message.answer(stats_text.strip(), parse_mode="HTML")
        logger.info(f"Админ {user_id} ({user_role}) запросил статистику платежей")

    except Exception as e:
        logger.error(f"Ошибка при получении статистики платежей для {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка при получении статистики платежей.")


@router.message(F.text == ReplyButtons.BROADCAST)
async def handle_broadcast(message: Message, db: Database):
    """Обработчик кнопки Рассылка"""
    try:
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        user_role = user.get('role', 'user') if user else 'user'

        # Проверяем права доступа
        if not TelegramUserPermissions.has_admin_access(user_id, user_role):
            await message.answer("❌ У вас нет прав для создания рассылок.")
            return

        broadcast_text = f"""
📢 <b>Рассылка сообщений</b>

🛡️ Ваша роль: {user_role}

📋 <b>Доступные команды:</b>
• /admin - Полная админ-панель с рассылкой
• Веб-админка: запустите run_admin.py

⚠️ <b>Внимание:</b>
Для создания рассылки используйте веб-админку или команду /admin для более удобного интерфейса.

💡 Веб-админка предоставляет расширенные возможности:
• Выбор целевой аудитории
• Предварительный просмотр
• Планирование рассылки
• Детальная статистика
        """

        await message.answer(
            broadcast_text.strip(),
            parse_mode="HTML"
        )

        logger.info(f"Админ {user_id} ({user_role}) открыл раздел рассылки")

    except Exception as e:
        logger.error(f"Ошибка при обработке рассылки для {message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при загрузке раздела рассылки.")


@router.message(F.text == ReplyButtons.USERS)
async def handle_users(message: Message, db: Database):
    """Обработчик кнопки Пользователи"""
    try:
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        user_role = user.get('role', 'user') if user else 'user'

        # Проверяем права доступа
        if not TelegramUserPermissions.has_admin_access(user_id, user_role):
            await message.answer("❌ У вас нет прав для управления пользователями.")
            return

        # Получаем базовую статистику пользователей
        stats = await db.get_stats()

        users_text = f"""
👥 <b>Управление пользователями</b>

📊 <b>Статистика:</b>
• Всего пользователей: {stats['total_users']}
• Активных подписчиков: {stats['active_subscribers']}
• Новых за сегодня: {stats.get('new_users_today', 0)}

🛡️ Ваша роль: {user_role}

📋 <b>Доступные команды:</b>
• /admin - Полная админ-панель
• Веб-админка: запустите run_admin.py

💡 <b>Веб-админка предоставляет:</b>
• Детальный список пользователей
• Управление подписками
• Блокировка/разблокировка
• Изменение ролей
• Детальная аналитика
        """

        await message.answer(
            users_text.strip(),
            parse_mode="HTML"
        )

        logger.info(f"Админ {user_id} ({user_role}) открыл управление пользователями")

    except Exception as e:
        logger.error(f"Ошибка при управлении пользователями для {message.from_user.id}: {e}")
        await message.answer("❌ Ошибка при загрузке управления пользователями.")


# Обработчик для неизвестных Reply кнопок
@router.message(F.text.func(lambda text: is_reply_button(text)))
async def handle_unknown_reply_button(message: Message):
    """Обработчик для неизвестных Reply кнопок"""
    logger.warning(f"Неизвестная Reply кнопка: {message.text} от пользователя {message.from_user.id}")
    await message.answer(
        "❓ Неизвестная команда. Используйте кнопки меню.",
        reply_markup=get_main_menu_keyboard()
    )
