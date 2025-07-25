"""
Обработчики для управления ролями пользователей
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models import Database
from bot.utils.roles import TelegramUserPermissions, TelegramUserRole, RoleHierarchy, log_role_action
from bot.middlewares.role_middleware import AdminOnlyMiddleware, get_user_role, get_user_permissions

logger = logging.getLogger(__name__)
router = Router()

# Применяем middleware только для администраторов
router.message.middleware(AdminOnlyMiddleware("❌ Управление ролями доступно только администраторам"))
router.callback_query.middleware(AdminOnlyMiddleware("❌ Управление ролями доступно только администраторам"))


class RoleManagementStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_new_role = State()


def get_role_management_keyboard():
    """Клавиатура управления ролями"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Список администраторов", callback_data="roles_list_admins"),
            InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="roles_find_user")
        ],
        [
            InlineKeyboardButton(text="🎭 Изменить роль", callback_data="roles_change_role"),
            InlineKeyboardButton(text="📊 Статистика ролей", callback_data="roles_stats")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")
        ]
    ])
    return keyboard


def get_role_selection_keyboard(current_role: str, manager_role: str):
    """Клавиатура выбора роли"""
    buttons = []
    
    for role in TelegramUserRole:
        # Проверяем, может ли текущий администратор назначить эту роль
        if RoleHierarchy.can_manage_role(manager_role, role.value):
            role_name = TelegramUserPermissions.get_role_display_name(role.value)
            emoji = "✅" if role.value == current_role else "⚪"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{emoji} {role_name}",
                    callback_data=f"set_role_{role.value}"
                )
            ])
    
    buttons.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="roles_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("roles"))
async def cmd_roles(message: Message, db: Database, **kwargs):
    """Команда управления ролями"""
    user_role = get_user_role(kwargs)
    
    await message.answer(
        f"🎭 <b>Управление ролями пользователей</b>\n\n"
        f"Ваша роль: {TelegramUserPermissions.get_role_display_name(user_role)}\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_role_management_keyboard()
    )


@router.callback_query(F.data == "roles_menu")
async def callback_roles_menu(callback: CallbackQuery, db: Database, **kwargs):
    """Главное меню управления ролями"""
    user_role = get_user_role(kwargs)
    
    await callback.message.edit_text(
        f"🎭 <b>Управление ролями пользователей</b>\n\n"
        f"Ваша роль: {TelegramUserPermissions.get_role_display_name(user_role)}\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_role_management_keyboard()
    )


@router.callback_query(F.data == "roles_list_admins")
async def callback_list_admins(callback: CallbackQuery, db: Database, **kwargs):
    """Список всех администраторов"""
    try:
        admins = await db.get_admin_users()
        
        if not admins:
            await callback.answer("Администраторы не найдены", show_alert=True)
            return
        
        text = "👥 <b>Список администраторов:</b>\n\n"
        
        for admin in admins:
            role_name = TelegramUserPermissions.get_role_display_name(admin['role'])
            name = admin.get('first_name', '') or admin.get('username', 'Без имени')
            text += f"• <b>{name}</b> (ID: {admin['user_id']})\n"
            text += f"  🎭 Роль: {role_name}\n"
            text += f"  📅 Регистрация: {admin['created_at'][:10]}\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="roles_menu")]
        ])
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка получения списка администраторов: {e}")
        await callback.answer("Ошибка получения данных", show_alert=True)


@router.callback_query(F.data == "roles_find_user")
async def callback_find_user(callback: CallbackQuery, state: FSMContext, **kwargs):
    """Поиск пользователя для изменения роли"""
    await state.set_state(RoleManagementStates.waiting_for_user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="roles_menu")]
    ])
    
    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Отправьте ID пользователя Telegram для поиска:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.message(RoleManagementStates.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext, db: Database, **kwargs):
    """Обработка введенного ID пользователя"""
    try:
        user_id = int(message.text.strip())
        
        # Получаем информацию о пользователе
        user_data = await db.get_user(user_id)
        
        if not user_data:
            await message.answer(
                "❌ Пользователь не найден в базе данных.\n"
                "Возможно, он еще не использовал бота."
            )
            return
        
        user_role = await db.get_user_role(user_id)
        role_name = TelegramUserPermissions.get_role_display_name(user_role)
        name = user_data.get('first_name', '') or user_data.get('username', 'Без имени')
        
        # Сохраняем ID пользователя в состоянии
        await state.update_data(target_user_id=user_id)
        await state.set_state(RoleManagementStates.waiting_for_new_role)
        
        manager_role = get_user_role(kwargs)
        
        text = f"👤 <b>Информация о пользователе:</b>\n\n"
        text += f"🆔 ID: {user_id}\n"
        text += f"👤 Имя: {name}\n"
        text += f"🎭 Текущая роль: {role_name}\n"
        text += f"📅 Регистрация: {user_data['created_at'][:10]}\n"
        text += f"🔍 Запросов: {user_data['requests_used']}\n\n"
        text += "Выберите новую роль:"
        
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_role_selection_keyboard(user_role, manager_role)
        )
        
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите числовой ID пользователя.")
    except Exception as e:
        logger.error(f"Ошибка поиска пользователя: {e}")
        await message.answer("❌ Произошла ошибка при поиске пользователя.")


@router.callback_query(F.data.startswith("set_role_"))
async def callback_set_role(callback: CallbackQuery, state: FSMContext, db: Database, **kwargs):
    """Установка новой роли пользователю"""
    try:
        new_role = callback.data.replace("set_role_", "")
        state_data = await state.get_data()
        target_user_id = state_data.get("target_user_id")
        
        if not target_user_id:
            await callback.answer("Ошибка: пользователь не выбран", show_alert=True)
            return
        
        manager_role = get_user_role(kwargs)
        manager_id = callback.from_user.id
        
        # Проверяем права на изменение роли
        if not RoleHierarchy.can_manage_role(manager_role, new_role):
            await callback.answer("❌ У вас нет прав для назначения этой роли", show_alert=True)
            return
        
        # Обновляем роль в базе данных
        success = await db.update_user_role(target_user_id, new_role)
        
        if success:
            role_name = TelegramUserPermissions.get_role_display_name(new_role)
            
            # Логируем действие
            log_role_action(
                manager_id,
                "ROLE_CHANGED",
                f"Changed user {target_user_id} role to {new_role}"
            )
            
            await callback.message.edit_text(
                f"✅ <b>Роль успешно изменена!</b>\n\n"
                f"Пользователь: {target_user_id}\n"
                f"Новая роль: {role_name}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 К управлению ролями", callback_data="roles_menu")]
                ])
            )
            
            await state.clear()
        else:
            await callback.answer("❌ Ошибка при изменении роли", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка изменения роли: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "roles_stats")
async def callback_roles_stats(callback: CallbackQuery, db: Database, **kwargs):
    """Статистика по ролям"""
    try:
        # Получаем статистику по каждой роли
        stats = {}
        for role in TelegramUserRole:
            users = await db.get_users_by_role(role.value)
            stats[role.value] = len(users)
        
        text = "📊 <b>Статистика по ролям:</b>\n\n"
        
        for role, count in stats.items():
            role_name = TelegramUserPermissions.get_role_display_name(role)
            text += f"🎭 {role_name}: {count} пользователей\n"
        
        total_users = sum(stats.values())
        text += f"\n📈 Всего пользователей с ролями: {total_users}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="roles_menu")]
        ])
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики ролей: {e}")
        await callback.answer("Ошибка получения статистики", show_alert=True)
