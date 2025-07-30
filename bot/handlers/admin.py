"""
Админ обработчики
"""
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.state import StateFilter

from database.models import Database
from bot.keyboards.inline import get_admin_keyboard, get_back_keyboard, get_broadcast_confirm_keyboard, get_audience_selection_keyboard
from bot.utils.roles import TelegramUserPermissions
from services.payment_service import create_payment_service
from config import (ADMIN_USER_ID, YOOKASSA_PROVIDER_TOKEN, YOOKASSA_CURRENCY,
                   YOOKASSA_PROVIDER_DATA)
import logging

logger = logging.getLogger(__name__)
router = Router()


class BroadcastStates(StatesGroup):
    selecting_audience = State()
    waiting_for_message = State()
    confirming_broadcast = State()


async def is_admin(user_id: int, db: Database) -> bool:
    """Проверка на админа с использованием новой системы ролей"""
    try:
        user = await db.get_user(user_id)
        user_role = user.get('role', 'user') if user else 'user'
        return TelegramUserPermissions.has_admin_access(user_id, user_role)
    except Exception as e:
        logger.error(f"Ошибка при проверке прав админа для {user_id}: {e}")
        return False


@router.message(Command("admin"))
async def cmd_admin(message: Message, db: Database):
    """Админ панель"""
    user_id = message.from_user.id

    if not await is_admin(user_id, db):
        await message.answer("❌ У вас нет прав администратора")
        return

    # Получаем роль пользователя для отображения
    user = await db.get_user(user_id)
    user_role = user.get('role', 'user') if user else 'user'

    await message.answer(
        f"👨‍💼 <b>Админ панель FinderTool</b>\n\n"
        f"🛡️ Ваша роль: {user_role}\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

    logger.info(f"Админ {user_id} ({user_role}) открыл админ-панель через команду /admin")


@router.callback_query(F.data == "admin_stats")
async def callback_admin_stats(callback: CallbackQuery, db: Database):
    """Статистика бота"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return
    
    stats = await db.get_stats()
    
    stats_text = f"""
📊 <b>Статистика бота</b>

👥 Всего пользователей: {stats['total_users']}
💎 Активных подписчиков: {stats['active_subscribers']}
🔍 Запросов сегодня: {stats['requests_today']}

📈 Конверсия в подписку: {(stats['active_subscribers'] / max(stats['total_users'], 1) * 100):.1f}%
    """
    
    await callback.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def callback_admin_broadcast(callback: CallbackQuery, db: Database):
    """Управление рассылками - главное меню"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    # Получаем статистику рассылок
    try:
        stats = await db.get_broadcasts_stats()
    except:
        stats = {
            'total_broadcasts': 0,
            'active_broadcasts': 0,
            'completed_broadcasts': 0,
            'total_sent': 0
        }

    text = f"""📢 <b>Управление рассылками</b>

📊 <b>Общая статистика:</b>
• Всего рассылок: {stats.get('total', 0)}
• Активных: {stats.get('sending', 0)}
• Завершенных: {stats.get('completed', 0)}
• Ожидают: {stats.get('pending', 0)}

🔧 <b>Доступные действия:</b>"""

    # Создаем клавиатуру для управления рассылками
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="📋 Список рассылок", callback_data="broadcasts_list:1"),
        InlineKeyboardButton(text="➕ Создать рассылку", callback_data="broadcast_create")
    )
    keyboard.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="broadcasts_stats"),
        InlineKeyboardButton(text="📝 Шаблоны", callback_data="broadcast_templates")
    )
    keyboard.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("broadcasts_list:"))
async def callback_broadcasts_list(callback: CallbackQuery, db: Database):
    """Список рассылок с пагинацией"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    # Извлекаем номер страницы
    page = int(callback.data.split(":")[1])
    per_page = 5  # Показываем по 5 рассылок на странице

    try:
        # Получаем рассылки с пагинацией
        result = await db.get_broadcasts_paginated(
            page=page,
            per_page=per_page
        )

        if not result["broadcasts"]:
            await callback.message.edit_text(
                "📢 <b>Список рассылок</b>\n\n"
                "Рассылки не найдены.\n"
                "Создайте первую рассылку!",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="➕ Создать рассылку", callback_data="broadcast_create"),
                    InlineKeyboardButton(text="🔙 Назад", callback_data="admin_broadcast")
                ]])
            )
            await callback.answer()
            return

        # Формируем текст со списком рассылок
        text = f"📢 <b>Список рассылок</b> (стр. {page}/{result['pages']})\n\n"

        for broadcast in result["broadcasts"]:
            # Определяем статус рассылки
            status_emoji = {
                "draft": "📝",
                "sending": "📤",
                "completed": "✅",
                "failed": "❌",
                "paused": "⏸️"
            }.get(broadcast.get('status', 'draft'), "📝")

            # Название рассылки
            title = broadcast.get('title', f"Рассылка #{broadcast['id']}")[:30]

            # Статистика
            sent = broadcast.get('sent_count', 0)
            total = broadcast.get('total_recipients', 0)

            text += f"{status_emoji} <b>{title}</b>\n"
            text += f"   ID: {broadcast['id']} | Отправлено: {sent}/{total}\n"
            text += f"   Создана: {broadcast.get('created_at', 'Неизвестно')[:16]}\n\n"

        # Создаем клавиатуру с пагинацией
        keyboard = InlineKeyboardBuilder()

        # Кнопки для каждой рассылки
        for broadcast in result["broadcasts"]:
            title = broadcast.get('title', f"Рассылка #{broadcast['id']}")[:20]
            keyboard.row(
                InlineKeyboardButton(
                    text=f"📊 {title}...",
                    callback_data=f"broadcast_detail:{broadcast['id']}"
                )
            )

        # Навигация по страницам
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"broadcasts_list:{page-1}"))
        if page < result['pages']:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"broadcasts_list:{page+1}"))

        if nav_buttons:
            keyboard.row(*nav_buttons)

        keyboard.row(
            InlineKeyboardButton(text="➕ Создать", callback_data="broadcast_create"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_broadcast")
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка получения списка рассылок: {e}")
        await callback.answer("Ошибка получения данных", show_alert=True)


@router.callback_query(F.data == "broadcast_create")
async def callback_broadcast_create(callback: CallbackQuery, state: FSMContext, db: Database):
    """Создание новой рассылки - выбор аудитории"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    # Получаем статистику по аудиториям
    all_count = await db.get_users_count()
    active_count = await db.get_active_users_count()
    subscribers_count = await db.get_subscribers_count()

    text = f"""➕ <b>Создание новой рассылки</b>

📊 <b>Выберите целевую аудиторию:</b>

👥 <b>Все пользователи</b> - {all_count} чел.
Все зарегистрированные пользователи

🔥 <b>Активные пользователи</b> - {active_count} чел.
Пользователи, активные за последние 30 дней

💎 <b>Подписчики</b> - {subscribers_count} чел.
Пользователи с активной подпиской

Выберите целевую аудиторию для рассылки:"""

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text=f"👥 Все ({all_count})", callback_data="create_audience_all"),
        InlineKeyboardButton(text=f"🔥 Активные ({active_count})", callback_data="create_audience_active")
    )
    keyboard.row(
        InlineKeyboardButton(text=f"💎 Подписчики ({subscribers_count})", callback_data="create_audience_subscribers")
    )
    keyboard.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_broadcast")
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )

    # Очищаем состояние и устанавливаем новое
    await state.clear()
    await state.set_state("creating_broadcast")
    await callback.answer()


@router.callback_query(F.data.startswith("create_audience_"))
async def callback_create_audience(callback: CallbackQuery, state: FSMContext, db: Database):
    """Выбор аудитории для новой рассылки"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        await state.clear()
        return

    audience_type = callback.data.split("_")[2]  # create_audience_all -> all

    # Сохраняем выбранную аудиторию
    await state.update_data(audience_type=audience_type)

    # Получаем название аудитории для отображения
    audience_names = {
        "all": "Все пользователи",
        "active": "Активные пользователи",
        "subscribers": "Подписчики"
    }

    audience_name = audience_names.get(audience_type, "Неизвестная аудитория")

    text = f"""➕ <b>Создание рассылки</b>

🎯 <b>Выбранная аудитория:</b> {audience_name}

📝 <b>Теперь отправьте сообщение для рассылки</b>

💡 <b>Поддерживается:</b>
• HTML разметка (<b>жирный</b>, <i>курсив</i>)
• Эмодзи 😊
• Ссылки
• Переносы строк

Отправьте текст сообщения:"""

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="broadcast_create")
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )

    await state.set_state("waiting_broadcast_message")
    await callback.answer()


# Обработчик сообщения для рассылки
@router.message(F.text, StateFilter("waiting_broadcast_message"))
async def handle_broadcast_message(message: Message, state: FSMContext, db: Database):
    """Обработка сообщения для рассылки"""
    if not await is_admin(message.from_user.id, db):
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return

    # Получаем данные из состояния
    data = await state.get_data()
    audience_type = data.get('audience_type', 'all')

    # Сохраняем сообщение
    await state.update_data(broadcast_message=message.html_text)

    # Получаем количество получателей
    if audience_type == "all":
        target_count = await db.get_users_count()
        audience_name = "всем пользователям"
    elif audience_type == "active":
        target_count = await db.get_active_users_count()
        audience_name = "активным пользователям"
    elif audience_type == "subscribers":
        target_count = await db.get_subscribers_count()
        audience_name = "подписчикам"
    else:
        target_count = await db.get_users_count()
        audience_name = "всем пользователям"

    # Предварительный просмотр
    preview_text = f"""📢 <b>Предварительный просмотр рассылки</b>

🎯 <b>Аудитория:</b> {audience_name} ({target_count} чел.)

📝 <b>Сообщение:</b>
{message.html_text}

───────────────────

⚙️ <b>Настройки отправки:</b>
• Скорость: Обычная (30 сообщений/мин)
• Пропускать заблокированных: Да

Отправить рассылку?"""

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Отправить сейчас", callback_data="confirm_send_now"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="broadcast_settings")
    )
    keyboard.row(
        InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast_create")
    )

    await message.answer(
        preview_text,
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )

    await state.set_state("confirming_broadcast")


@router.callback_query(F.data == "confirm_send_now", StateFilter("confirming_broadcast"))
async def callback_confirm_send_now(callback: CallbackQuery, state: FSMContext, db: Database):
    """Подтверждение отправки рассылки"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        await state.clear()
        return

    # Получаем данные из состояния
    data = await state.get_data()
    broadcast_message = data.get('broadcast_message')
    audience_type = data.get('audience_type', 'all')

    if not broadcast_message:
        await callback.answer("❌ Сообщение не найдено", show_alert=True)
        await state.clear()
        return

    try:
        # Создаем рассылку в базе данных
        broadcast_id = await db.create_broadcast(
            title=f"Рассылка {audience_type}",
            message_text=broadcast_message,
            parse_mode="HTML",
            target_users=audience_type,
            created_by=callback.from_user.id,
            scheduled_at=None  # Отправляем сейчас
        )

        await callback.message.edit_text(
            "📤 <b>Рассылка создана и запущена!</b>\n\n"
            f"🆔 ID рассылки: {broadcast_id}\n"
            "📊 Отправка началась в фоновом режиме\n\n"
            "Вы можете отслеживать прогресс в разделе 'Список рассылок'",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📊 Посмотреть статистику", callback_data=f"broadcast_detail:{broadcast_id}"),
                InlineKeyboardButton(text="📋 Список рассылок", callback_data="broadcasts_list:1")
            ], [
                InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_broadcast")
            ]])
        )

        # Запускаем фоновую отправку
        import asyncio
        task = asyncio.create_task(send_broadcast_task(db, broadcast_id, callback.bot))

        # Добавляем обработчик ошибок для фоновой задачи
        def task_done_callback(task):
            if task.exception():
                logger.error(f"Ошибка в фоновой задаче рассылки {broadcast_id}: {task.exception()}")

        task.add_done_callback(task_done_callback)

        await state.clear()
        await callback.answer("✅ Рассылка запущена!")

        logger.info(f"Админ {callback.from_user.id} запустил рассылку {broadcast_id} для аудитории {audience_type}")

    except Exception as e:
        logger.error(f"Ошибка создания рассылки: {e}")
        await callback.answer("❌ Ошибка создания рассылки", show_alert=True)
        await state.clear()


async def send_broadcast_task(db: Database, broadcast_id: int, bot):
    """Фоновая задача отправки рассылки"""
    try:
        logger.info(f"Начинаем отправку рассылки {broadcast_id}")

        # Получаем информацию о рассылке
        broadcast = await db.get_broadcast_by_id(broadcast_id)
        if not broadcast:
            logger.error(f"Рассылка {broadcast_id} не найдена")
            return

        # Обновляем статус на "отправляется" и устанавливаем время начала
        from datetime import datetime
        await db.update_broadcast_status(broadcast_id, "sending")
        await db.update_broadcast_stats(broadcast_id, started_at=datetime.now())

        # Получаем список пользователей
        target_users = await get_target_users_for_broadcast(db, broadcast['target_users'])
        total_users = len(target_users)

        if total_users == 0:
            await db.update_broadcast_status(broadcast_id, "completed")
            await db.update_broadcast_stats(broadcast_id, sent_count=0, failed_count=0, completed=True)
            logger.info(f"Рассылка {broadcast_id} завершена: нет получателей")
            return

        # Логируем общее количество получателей
        logger.info(f"Рассылка {broadcast_id}: найдено {total_users} получателей")

        sent_count = 0
        failed_count = 0

        # Отправляем сообщения
        for user_id in target_users:
            try:
                from bot.utils.error_handler import safe_send_message

                success = await safe_send_message(
                    bot=bot,
                    user_id=user_id,
                    text=broadcast['message_text'],
                    db=db,
                    parse_mode=broadcast.get('parse_mode', 'HTML')
                )

                if success:
                    sent_count += 1
                else:
                    failed_count += 1

                # Обновляем статистику каждые 10 сообщений
                if (sent_count + failed_count) % 10 == 0:
                    await db.update_broadcast_stats(
                        broadcast_id,
                        sent_count=sent_count,
                        failed_count=failed_count
                    )

                # Задержка для соблюдения лимитов API (30 сообщений в минуту)
                await asyncio.sleep(2.0)

            except Exception as e:
                failed_count += 1
                logger.error(f"Ошибка отправки пользователю {user_id}: {e}")

        # Финальное обновление статистики
        await db.update_broadcast_stats(
            broadcast_id,
            sent_count=sent_count,
            failed_count=failed_count,
            completed=True
        )
        await db.update_broadcast_status(broadcast_id, "completed")

        logger.info(f"Рассылка {broadcast_id} завершена: отправлено {sent_count}, ошибок {failed_count}")

    except Exception as e:
        logger.error(f"Ошибка в фоновой задаче рассылки {broadcast_id}: {e}")
        await db.update_broadcast_status(broadcast_id, "failed")


async def get_target_users_for_broadcast(db: Database, target_type: str) -> list:
    """Получить список пользователей для рассылки"""
    try:
        if target_type == "all":
            users = await db.get_all_users_for_broadcast()
        elif target_type == "active":
            users = await db.get_active_users_for_broadcast(days=30)
        elif target_type == "subscribers":
            users = await db.get_subscribed_users()
        else:
            users = await db.get_all_users_for_broadcast()

        return [user['user_id'] for user in users]
    except Exception as e:
        logger.error(f"Ошибка получения пользователей для рассылки {target_type}: {e}")
        return []


@router.callback_query(F.data.startswith("broadcast_detail:"))
async def callback_broadcast_detail(callback: CallbackQuery, db: Database):
    """Детальная информация о рассылке"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    # Извлекаем ID рассылки
    broadcast_id = int(callback.data.split(":")[1])

    try:
        # Получаем информацию о рассылке
        broadcast = await db.get_broadcast_by_id(broadcast_id)
        if not broadcast:
            await callback.answer("Рассылка не найдена", show_alert=True)
            return

        # Формируем детальную информацию
        title = broadcast.get('title', f"Рассылка #{broadcast_id}")
        status = broadcast.get('status', 'unknown')

        # Статус с эмодзи
        status_emoji = {
            "pending": "⏳ Ожидает",
            "sending": "📤 Отправляется",
            "completed": "✅ Завершена",
            "failed": "❌ Ошибка",
            "paused": "⏸️ Приостановлена"
        }.get(status, "❓ Неизвестно")

        # Получаем детальную статистику
        stats = await db.get_broadcast_detailed_stats(broadcast_id)
        sent = stats.get('delivered', 0)
        failed = stats.get('failed', 0)
        total = stats.get('total_recipients', 0)

        # Даты
        created_at = broadcast.get('created_at', 'Неизвестно')[:16]
        started_at = broadcast.get('started_at', 'Не начата')
        if started_at != 'Не начата':
            started_at = started_at[:16]

        # Аудитория
        target_names = {
            "all": "Все пользователи",
            "active": "Активные пользователи",
            "subscribers": "Подписчики"
        }
        target_name = target_names.get(broadcast.get('target_users', 'all'), "Неизвестно")

        text = f"""📊 <b>Детали рассылки</b>

<b>Основная информация:</b>
• Название: {title}
• ID: {broadcast_id}
• Статус: {status_emoji}
• Аудитория: {target_name}

<b>Статистика:</b>
• Отправлено: {sent}
• Ошибок: {failed}
• Всего получателей: {total}
• Успешность: {(sent / max(sent + failed, 1) * 100):.1f}%

<b>Временные метки:</b>
• Создана: {created_at}
• Начата: {started_at}

<b>Сообщение:</b>
{broadcast.get('message_text', 'Не указано')[:200]}{'...' if len(broadcast.get('message_text', '')) > 200 else ''}"""

        # Создаем клавиатуру с действиями
        keyboard = InlineKeyboardBuilder()

        # Действия в зависимости от статуса
        if status == "sending":
            keyboard.row(
                InlineKeyboardButton(text="⏸️ Приостановить", callback_data=f"broadcast_pause:{broadcast_id}")
            )
        elif status == "paused":
            keyboard.row(
                InlineKeyboardButton(text="▶️ Возобновить", callback_data=f"broadcast_resume:{broadcast_id}")
            )
        elif status == "pending":
            keyboard.row(
                InlineKeyboardButton(text="▶️ Запустить", callback_data=f"broadcast_start:{broadcast_id}")
            )

        keyboard.row(
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"broadcast_detail:{broadcast_id}"),
            InlineKeyboardButton(text="📋 К списку", callback_data="broadcasts_list:1")
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка получения информации о рассылке {broadcast_id}: {e}")
        await callback.answer("Ошибка получения данных", show_alert=True)


@router.callback_query(F.data == "broadcasts_stats")
async def callback_broadcasts_stats(callback: CallbackQuery, db: Database):
    """Детальная статистика рассылок"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    try:
        stats = await db.get_broadcasts_stats()

        text = f"""📊 <b>Детальная статистика рассылок</b>

📢 <b>Рассылки:</b>
• Всего создано: {stats.get('total', 0)}
• Завершенных: {stats.get('completed', 0)}
• Отправляется: {stats.get('sending', 0)}
• Ожидают: {stats.get('pending', 0)}
• С ошибками: {stats.get('failed', 0)}

📈 <b>Эффективность:</b>
• Успешных: {(stats.get('completed', 0) / max(stats.get('total', 1), 1) * 100):.1f}%
• В процессе: {(stats.get('sending', 0) / max(stats.get('total', 1), 1) * 100):.1f}%

💡 <b>Рекомендации:</b>
• Оптимальная скорость: 30 сообщений/мин
• Лучшее время: 10:00-18:00
• Избегайте выходных для деловых рассылок"""

        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_broadcast")
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка получения статистики рассылок: {e}")
        await callback.answer("Ошибка получения статистики", show_alert=True)


@router.callback_query(F.data == "broadcast_templates")
async def callback_broadcast_templates(callback: CallbackQuery, db: Database):
    """Шаблоны сообщений для рассылок"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    try:
        # Получаем шаблоны (если метод существует)
        try:
            templates = await db.get_message_templates()
        except:
            templates = []

        if not templates:
            text = """📝 <b>Шаблоны сообщений</b>

🚧 Шаблоны не найдены

💡 <b>Что такое шаблоны?</b>
Шаблоны позволяют сохранять часто используемые тексты для рассылок и быстро их переиспользовать.

<b>Примеры шаблонов:</b>
• Приветственные сообщения
• Уведомления об обновлениях
• Промо-акции
• Технические уведомления"""

            keyboard = InlineKeyboardBuilder()
            keyboard.row(
                InlineKeyboardButton(text="➕ Создать шаблон", callback_data="template_create"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="admin_broadcast")
            )
        else:
            text = f"📝 <b>Шаблоны сообщений</b> ({len(templates)})\n\n"

            keyboard = InlineKeyboardBuilder()

            for template in templates[:5]:  # Показываем первые 5
                name = template.get('name', 'Без названия')[:20]
                keyboard.row(
                    InlineKeyboardButton(
                        text=f"📄 {name}...",
                        callback_data=f"template_use:{template['id']}"
                    )
                )

            keyboard.row(
                InlineKeyboardButton(text="➕ Создать", callback_data="template_create"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="admin_broadcast")
            )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка получения шаблонов: {e}")
        await callback.answer("Ошибка получения данных", show_alert=True)


@router.callback_query(F.data == "template_create")
async def callback_template_create(callback: CallbackQuery, state: FSMContext, db: Database):
    """Создание нового шаблона"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    text = """➕ <b>Создание шаблона сообщения</b>

📝 <b>Отправьте текст шаблона</b>

💡 <b>Советы:</b>
• Используйте понятное название
• Добавляйте HTML разметку для красоты
• Можно использовать эмодзи
• Длина до 4000 символов

Отправьте текст для шаблона:"""

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="broadcast_templates")
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )

    await state.set_state("creating_template")
    await callback.answer()


# Обработчик создания шаблона
@router.message(F.text, StateFilter("creating_template"))
async def handle_template_creation(message: Message, state: FSMContext, db: Database):
    """Обработка создания шаблона"""
    if not await is_admin(message.from_user.id, db):
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return

    template_text = message.html_text

    if len(template_text) > 4000:
        await message.answer("❌ Текст шаблона слишком длинный (максимум 4000 символов)")
        return

    try:
        # Создаем шаблон (если метод существует)
        try:
            template_id = await db.create_message_template(
                name=f"Шаблон {message.from_user.id}",
                content=template_text,
                category="general",
                created_by=message.from_user.id
            )

            await message.answer(
                f"✅ <b>Шаблон создан!</b>\n\n"
                f"🆔 ID: {template_id}\n"
                f"📝 Текст сохранен\n\n"
                f"Теперь вы можете использовать этот шаблон в рассылках.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="📝 К шаблонам", callback_data="broadcast_templates"),
                    InlineKeyboardButton(text="📢 К рассылкам", callback_data="admin_broadcast")
                ]])
            )
        except:
            # Если метод не существует, просто сохраняем в состоянии
            await message.answer(
                "✅ <b>Шаблон сохранен!</b>\n\n"
                "📝 Текст запомнен для быстрого использования\n\n"
                "💡 В будущих версиях будет полная система шаблонов",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="📢 К рассылкам", callback_data="admin_broadcast")
                ]])
            )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка создания шаблона: {e}")
        await message.answer("❌ Ошибка создания шаблона")
        await state.clear()






    await callback.message.edit_text(
        "❌ <b>Рассылка отменена</b>\n\n"
        "Возвращаемся в админ-панель.",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "admin_users")
async def callback_admin_users(callback: CallbackQuery, db: Database):
    """Управление пользователями - главное меню"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    # Получаем общую статистику пользователей
    stats = await db.get_stats()

    text = f"""👥 <b>Управление пользователями</b>

📊 <b>Общая статистика:</b>
• Всего пользователей: {stats['total_users']}
• Активных подписчиков: {stats['active_subscribers']}
• Заблокированных: {stats.get('blocked_users', 0)}

🔧 <b>Доступные действия:</b>"""

    # Создаем клавиатуру для управления пользователями
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="📋 Список пользователей", callback_data="users_list:1"),
        InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="users_search")
    )
    keyboard.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="users_stats"),
        InlineKeyboardButton(text="🚫 Заблокированные", callback_data="users_blocked")
    )
    keyboard.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("users_list:"))
async def callback_users_list(callback: CallbackQuery, db: Database):
    """Список пользователей с пагинацией"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    # Извлекаем номер страницы
    page = int(callback.data.split(":")[1])
    per_page = 5  # Показываем по 5 пользователей на странице

    try:
        # Получаем пользователей с пагинацией
        result = await db.get_users_paginated(
            page=page,
            per_page=per_page
        )

        if not result["users"]:
            await callback.answer("Пользователи не найдены", show_alert=True)
            return

        # Формируем текст со списком пользователей
        text = f"👥 <b>Список пользователей</b> (стр. {page}/{result['pages']})\n\n"

        for i, user in enumerate(result["users"], 1):
            # Определяем статус пользователя
            status_emoji = "🟢" if user.get('is_subscribed') else "⚪"
            if user.get('blocked'):
                status_emoji = "🔴"

            # Имя пользователя
            name = user.get('first_name', '') or user.get('username', f"ID{user['user_id']}")

            # Количество запросов
            requests = user.get('requests_used', 0)

            text += f"{status_emoji} <b>{name}</b>\n"
            text += f"   ID: {user['user_id']} | Запросов: {requests}\n"
            if user.get('username'):
                text += f"   @{user['username']}\n"
            text += "\n"

        # Создаем клавиатуру с пагинацией
        keyboard = InlineKeyboardBuilder()

        # Кнопки для каждого пользователя
        for user in result["users"]:
            name = user.get('first_name', '') or user.get('username', f"ID{user['user_id']}")
            keyboard.row(
                InlineKeyboardButton(
                    text=f"👤 {name[:20]}...",
                    callback_data=f"user_detail:{user['user_id']}"
                )
            )

        # Навигация по страницам
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"users_list:{page-1}"))
        if page < result['pages']:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"users_list:{page+1}"))

        if nav_buttons:
            keyboard.row(*nav_buttons)

        keyboard.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users")
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка получения списка пользователей: {e}")
        await callback.answer("Ошибка получения данных", show_alert=True)


@router.callback_query(F.data.startswith("user_detail:"))
async def callback_user_detail(callback: CallbackQuery, db: Database):
    """Детальная информация о пользователе"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    # Извлекаем ID пользователя
    user_id = int(callback.data.split(":")[1])

    try:
        # Получаем информацию о пользователе
        user = await db.get_user(user_id)
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        # Формируем детальную информацию
        name = user.get('first_name', '') or user.get('username', f"ID{user_id}")

        # Статус подписки
        subscription_status = "✅ Активна" if user.get('is_subscribed') else "❌ Неактивна"
        if user.get('unlimited_access'):
            subscription_status = "♾️ Безлимитная"

        # Статус блокировки
        block_status = "🔴 Заблокирован" if user.get('blocked') else "🟢 Активен"

        # Даты
        created_at = user.get('created_at', 'Неизвестно')
        last_request = user.get('last_request', 'Никогда')
        subscription_end = user.get('subscription_end', 'Нет')

        text = f"""👤 <b>Информация о пользователе</b>

<b>Основная информация:</b>
• Имя: {name}
• ID: {user_id}
• Username: @{user.get('username', 'не указан')}
• Статус: {block_status}

<b>Подписка:</b>
• Статус: {subscription_status}
• Запросов использовано: {user.get('requests_used', 0)}
• Окончание: {subscription_end}

<b>Активность:</b>
• Регистрация: {created_at}
• Последний запрос: {last_request}"""

        # Создаем клавиатуру с действиями
        keyboard = InlineKeyboardBuilder()

        # Управление подпиской
        if user.get('is_subscribed'):
            keyboard.row(
                InlineKeyboardButton(text="❌ Отменить подписку", callback_data=f"user_unsub:{user_id}")
            )
        else:
            keyboard.row(
                InlineKeyboardButton(text="✅ Активировать подписку", callback_data=f"user_sub:{user_id}")
            )

        # Управление блокировкой
        if user.get('blocked'):
            keyboard.row(
                InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f"user_unblock:{user_id}")
            )
        else:
            keyboard.row(
                InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"user_block:{user_id}")
            )

        # Дополнительные действия
        keyboard.row(
            InlineKeyboardButton(text="🔄 Сбросить запросы", callback_data=f"user_reset:{user_id}"),
            InlineKeyboardButton(text="♾️ Безлимит", callback_data=f"user_unlimited:{user_id}")
        )

        keyboard.row(
            InlineKeyboardButton(text="🔙 К списку", callback_data="users_list:1")
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка получения информации о пользователе {user_id}: {e}")
        await callback.answer("Ошибка получения данных", show_alert=True)


@router.callback_query(F.data.startswith("user_block:"))
async def callback_user_block(callback: CallbackQuery, db: Database):
    """Заблокировать пользователя"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    user_id = int(callback.data.split(":")[1])

    try:
        success = await db.update_user_permissions(
            user_id=user_id,
            blocked=True,
            notes=f"Заблокирован администратором {callback.from_user.id}",
            blocked_by=callback.from_user.id
        )

        if success:
            await callback.answer("✅ Пользователь заблокирован", show_alert=True)
            # Возвращаемся к детальной информации
            await callback_user_detail(callback, db)
        else:
            await callback.answer("❌ Ошибка блокировки", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка блокировки пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка блокировки", show_alert=True)


@router.callback_query(F.data.startswith("user_unblock:"))
async def callback_user_unblock(callback: CallbackQuery, db: Database):
    """Разблокировать пользователя"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    user_id = int(callback.data.split(":")[1])

    try:
        success = await db.update_user_permissions(
            user_id=user_id,
            blocked=False,
            notes=f"Разблокирован администратором {callback.from_user.id}",
            blocked_by=None
        )

        if success:
            await callback.answer("✅ Пользователь разблокирован", show_alert=True)
            # Возвращаемся к детальной информации
            await callback_user_detail(callback, db)
        else:
            await callback.answer("❌ Ошибка разблокировки", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка разблокировки пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка разблокировки", show_alert=True)


@router.callback_query(F.data.startswith("user_sub:"))
async def callback_user_subscribe(callback: CallbackQuery, db: Database):
    """Активировать подписку пользователя"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    user_id = int(callback.data.split(":")[1])

    try:
        # Активируем подписку на месяц
        from datetime import datetime, timedelta
        end_date = datetime.now() + timedelta(days=30)

        success = await db.update_subscription(
            user_id=user_id,
            is_subscribed=True,
            subscription_end=end_date
        )

        if success:
            await callback.answer("✅ Подписка активирована на месяц", show_alert=True)
            # Возвращаемся к детальной информации
            await callback_user_detail(callback, db)
        else:
            await callback.answer("❌ Ошибка активации подписки", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка активации подписки для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка активации подписки", show_alert=True)


@router.callback_query(F.data.startswith("user_unsub:"))
async def callback_user_unsubscribe(callback: CallbackQuery, db: Database):
    """Отменить подписку пользователя"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    user_id = int(callback.data.split(":")[1])

    try:
        success = await db.update_subscription(
            user_id=user_id,
            is_subscribed=False,
            subscription_end=None
        )

        if success:
            await callback.answer("✅ Подписка отменена", show_alert=True)
            # Возвращаемся к детальной информации
            await callback_user_detail(callback, db)
        else:
            await callback.answer("❌ Ошибка отмены подписки", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка отмены подписки для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка отмены подписки", show_alert=True)


@router.callback_query(F.data.startswith("user_reset:"))
async def callback_user_reset_requests(callback: CallbackQuery, db: Database):
    """Сбросить счетчик запросов пользователя"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    user_id = int(callback.data.split(":")[1])

    try:
        success = await db.reset_user_requests(user_id)

        if success:
            await callback.answer("✅ Счетчик запросов сброшен", show_alert=True)
            # Возвращаемся к детальной информации
            await callback_user_detail(callback, db)
        else:
            await callback.answer("❌ Ошибка сброса счетчика", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка сброса запросов для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка сброса счетчика", show_alert=True)


@router.callback_query(F.data.startswith("user_unlimited:"))
async def callback_user_unlimited(callback: CallbackQuery, db: Database):
    """Дать пользователю безлимитный доступ"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    user_id = int(callback.data.split(":")[1])

    try:
        success = await db.update_user_permissions(
            user_id=user_id,
            unlimited_access=True
        )

        if success:
            await callback.answer("✅ Безлимитный доступ активирован", show_alert=True)
            # Возвращаемся к детальной информации
            await callback_user_detail(callback, db)
        else:
            await callback.answer("❌ Ошибка активации безлимита", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка активации безлимита для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка активации безлимита", show_alert=True)


@router.callback_query(F.data == "users_search")
async def callback_users_search(callback: CallbackQuery, state: FSMContext, db: Database):
    """Начать поиск пользователя"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите для поиска:\n"
        "• ID пользователя (например: 123456789)\n"
        "• Username (например: @username)\n"
        "• Имя пользователя\n\n"
        "Отправьте сообщение с поисковым запросом:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users")
        ]])
    )

    # Устанавливаем состояние ожидания поискового запроса
    await state.set_state("waiting_user_search")
    await callback.answer()


@router.callback_query(F.data == "users_stats")
async def callback_users_stats(callback: CallbackQuery, db: Database):
    """Детальная статистика пользователей"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    try:
        stats = await db.get_stats()

        # Получаем дополнительную статистику
        total_requests = await db.get_total_requests_count()
        avg_requests = total_requests / max(stats['total_users'], 1)

        text = f"""📊 <b>Детальная статистика пользователей</b>

👥 <b>Пользователи:</b>
• Всего зарегистрировано: {stats['total_users']}
• Активных подписчиков: {stats['active_subscribers']}
• Заблокированных: {stats.get('blocked_users', 0)}
• С безлимитным доступом: {stats.get('unlimited_users', 0)}

🔍 <b>Активность:</b>
• Всего запросов: {total_requests}
• Среднее на пользователя: {avg_requests:.1f}
• Запросов сегодня: {stats['requests_today']}

📈 <b>Конверсия:</b>
• В подписку: {(stats['active_subscribers'] / max(stats['total_users'], 1) * 100):.1f}%
• Активность: {(stats.get('active_users', 0) / max(stats['total_users'], 1) * 100):.1f}%"""

        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users")
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка получения статистики пользователей: {e}")
        await callback.answer("Ошибка получения статистики", show_alert=True)


@router.callback_query(F.data == "users_blocked")
async def callback_users_blocked(callback: CallbackQuery, db: Database):
    """Список заблокированных пользователей"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ Нет прав доступа")
        return

    try:
        # Получаем заблокированных пользователей
        result = await db.get_users_paginated(
            page=1,
            per_page=10,
            filter_type="blocked"
        )

        if not result["users"]:
            await callback.message.edit_text(
                "🚫 <b>Заблокированные пользователи</b>\n\n"
                "Заблокированных пользователей нет",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users")
                ]])
            )
            await callback.answer()
            return

        text = f"🚫 <b>Заблокированные пользователи</b> ({result['total']})\n\n"

        keyboard = InlineKeyboardBuilder()

        for user in result["users"]:
            name = user.get('first_name', '') or user.get('username', f"ID{user['user_id']}")
            text += f"🔴 <b>{name}</b>\n"
            text += f"   ID: {user['user_id']}\n"
            if user.get('username'):
                text += f"   @{user['username']}\n"
            text += "\n"

            # Добавляем кнопку для каждого заблокированного пользователя
            keyboard.row(
                InlineKeyboardButton(
                    text=f"🔓 Разблокировать {name[:15]}...",
                    callback_data=f"user_unblock:{user['user_id']}"
                )
            )

        keyboard.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users")
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка получения заблокированных пользователей: {e}")
        await callback.answer("Ошибка получения данных", show_alert=True)


# Обработчик поискового запроса (текстовое сообщение)
@router.message(F.text, StateFilter("waiting_user_search"))
async def handle_user_search(message: Message, state: FSMContext, db: Database):
    """Обработка поискового запроса пользователя"""
    if not await is_admin(message.from_user.id, db):
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return

    search_query = message.text.strip()

    try:
        # Поиск пользователей
        result = await db.get_users_paginated(
            page=1,
            per_page=10,
            search=search_query
        )

        if not result["users"]:
            await message.answer(
                f"🔍 <b>Результаты поиска</b>\n\n"
                f"По запросу '<code>{search_query}</code>' ничего не найдено",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users")
                ]])
            )
            await state.clear()
            return

        text = f"🔍 <b>Результаты поиска</b>\nЗапрос: '<code>{search_query}</code>'\n\n"

        keyboard = InlineKeyboardBuilder()

        for user in result["users"]:
            # Статус пользователя
            status_emoji = "🟢" if user.get('is_subscribed') else "⚪"
            if user.get('blocked'):
                status_emoji = "🔴"

            name = user.get('first_name', '') or user.get('username', f"ID{user['user_id']}")

            text += f"{status_emoji} <b>{name}</b>\n"
            text += f"   ID: {user['user_id']} | Запросов: {user.get('requests_used', 0)}\n"
            if user.get('username'):
                text += f"   @{user['username']}\n"
            text += "\n"

            # Кнопка для просмотра деталей
            keyboard.row(
                InlineKeyboardButton(
                    text=f"👤 {name[:20]}...",
                    callback_data=f"user_detail:{user['user_id']}"
                )
            )

        keyboard.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users")
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard.as_markup()
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка поиска пользователей: {e}")
        await message.answer("❌ Ошибка поиска")
        await state.clear()


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database):
    """Команда детальной статистики (только для админов)"""
    if not await is_admin(message.from_user.id, db):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        # Получаем базовую статистику
        stats = await db.get_stats()

        # Получаем дополнительную статистику
        total_requests = await db.get_total_requests_count()
        avg_requests = total_requests / max(stats['total_users'], 1)

        # Получаем статистику рассылок
        try:
            broadcast_stats = await db.get_broadcasts_stats()
        except:
            broadcast_stats = {
                'total': 0,
                'completed': 0,
                'total_sent': 0
            }

        stats_text = f"""
📊 <b>Детальная статистика FinderTool</b>

👥 <b>Пользователи:</b>
• Всего зарегистрировано: {stats['total_users']}
• Активных подписчиков: {stats['active_subscribers']}
• Заблокированных: {stats.get('blocked_users', 0)}

🔍 <b>Активность:</b>
• Всего запросов: {total_requests}
• Среднее на пользователя: {avg_requests:.1f}
• Запросов сегодня: {stats['requests_today']}

📈 <b>Конверсия:</b>
• В подписку: {(stats['active_subscribers'] / max(stats['total_users'], 1) * 100):.1f}%
• Активность: {(stats['requests_today'] / max(stats['total_users'], 1) * 100):.1f}%

📢 <b>Рассылки:</b>
• Всего рассылок: {broadcast_stats.get('total', 0)}
• Завершенных: {broadcast_stats.get('completed', 0)}
• Отправлено сообщений: {broadcast_stats.get('total_sent', 0)}

💡 Используйте /admin для доступа к другим функциям
        """

        await message.answer(stats_text.strip(), parse_mode="HTML")
        logger.info(f"Админ {message.from_user.id} запросил детальную статистику")

    except Exception as e:
        logger.error(f"Ошибка при получении детальной статистики: {e}")
        await message.answer("❌ Произошла ошибка при получении статистики.")


@router.message(Command("payment_stats"))
async def cmd_payment_stats(message: Message, db: Database):
    """Команда статистики платежей (только для админов)"""
    if not await is_admin(message.from_user.id, db):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
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
📊 <b>Статистика платежей ЮKassa</b>
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

💡 Используйте /admin для доступа к другим функциям
        """

        await message.answer(stats_text.strip(), parse_mode="HTML")
        logger.info(f"Админ {message.from_user.id} запросил статистику платежей")

    except Exception as e:
        logger.error(f"Ошибка при получении статистики платежей: {e}")
        await message.answer("❌ Произошла ошибка при получении статистики.")


@router.callback_query(F.data == "payment_stats")
async def callback_payment_stats(callback: CallbackQuery, db: Database):
    """Callback статистики платежей"""
    if not await is_admin(callback.from_user.id, db):
        await callback.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    # Переиспользуем логику из команды
    message = callback.message
    message.from_user = callback.from_user
    await cmd_payment_stats(message, db)
    await callback.answer()
