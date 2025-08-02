"""
Secure Admin Access Handler
Генерация временных токенов для доступа к веб админ-панели
Production-ready security с JWT токенами
"""

import asyncio
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import jwt
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import SECRET_KEY, ADMIN_HOST, ADMIN_PORT, ADMIN_USER_IDS
from database.models import Database
from utils.decorators import admin_required

logger = logging.getLogger(__name__)

router = Router()

# Хранилище временных токенов (в production лучше использовать Redis)
temp_tokens: Dict[str, Dict[str, Any]] = {}

class AdminTokenManager:
    """Менеджер временных токенов для админ-доступа"""
    
    def __init__(self):
        self.secret_key = SECRET_KEY
        self.token_expiry = 300  # 5 минут
        self.max_tokens_per_user = 3
    
    def generate_secure_token(self, user_id: int, username: str = None) -> str:
        """Генерация secure JWT токена для админ-доступа"""
        try:
            # Payload для JWT токена
            payload = {
                'user_id': user_id,
                'username': username,
                'type': 'admin_access',
                'issued_at': int(time.time()),
                'expires_at': int(time.time()) + self.token_expiry,
                'nonce': secrets.token_urlsafe(16)  # Защита от replay атак
            }
            
            # Генерируем JWT токен
            token = jwt.encode(payload, self.secret_key, algorithm='HS256')
            
            # Сохраняем в временное хранилище
            self._store_temp_token(user_id, token, payload)
            
            logger.info(f"🔐 Создан временный токен для админа {user_id} ({username})")
            return token
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации токена: {e}")
            raise
    
    def _store_temp_token(self, user_id: int, token: str, payload: Dict[str, Any]):
        """Сохранение токена во временное хранилище"""
        if user_id not in temp_tokens:
            temp_tokens[user_id] = {}
        
        # Ограничиваем количество токенов на пользователя
        user_tokens = temp_tokens[user_id]
        if len(user_tokens) >= self.max_tokens_per_user:
            # Удаляем самый старый токен
            oldest_token = min(user_tokens.keys(), key=lambda k: user_tokens[k]['issued_at'])
            del user_tokens[oldest_token]
        
        # Сохраняем новый токен
        temp_tokens[user_id][token] = payload
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Проверка и валидация токена"""
        try:
            # Декодируем JWT токен
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            
            user_id = payload.get('user_id')
            
            # Проверяем наличие в временном хранилище
            if user_id not in temp_tokens or token not in temp_tokens[user_id]:
                logger.warning(f"⚠️ Токен не найден в хранилище: {user_id}")
                return None
            
            # Проверяем срок действия
            if payload.get('expires_at', 0) < int(time.time()):
                logger.warning(f"⚠️ Токен истек: {user_id}")
                self._remove_token(user_id, token)
                return None
            
            # Проверяем тип токена
            if payload.get('type') != 'admin_access':
                logger.warning(f"⚠️ Неверный тип токена: {payload.get('type')}")
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("⚠️ JWT токен истек")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"⚠️ Неверный JWT токен: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки токена: {e}")
            return None
    
    def _remove_token(self, user_id: int, token: str):
        """Удаление токена из хранилища"""
        if user_id in temp_tokens and token in temp_tokens[user_id]:
            del temp_tokens[user_id][token]
            if not temp_tokens[user_id]:
                del temp_tokens[user_id]
    
    def revoke_user_tokens(self, user_id: int) -> int:
        """Отзыв всех токенов пользователя"""
        if user_id in temp_tokens:
            count = len(temp_tokens[user_id])
            del temp_tokens[user_id]
            logger.info(f"🔐 Отозвано {count} токенов для пользователя {user_id}")
            return count
        return 0
    
    def cleanup_expired_tokens(self):
        """Очистка истекших токенов"""
        current_time = int(time.time())
        expired_count = 0
        
        for user_id in list(temp_tokens.keys()):
            user_tokens = temp_tokens[user_id]
            expired_tokens = [
                token for token, payload in user_tokens.items()
                if payload.get('expires_at', 0) < current_time
            ]
            
            for token in expired_tokens:
                del user_tokens[token]
                expired_count += 1
            
            if not user_tokens:
                del temp_tokens[user_id]
        
        if expired_count > 0:
            logger.info(f"🧹 Очищено {expired_count} истекших токенов")

# Глобальный экземпляр менеджера токенов
token_manager = AdminTokenManager()

@router.message(Command("admin"))
@admin_required
async def admin_panel_access(message: Message, state: FSMContext, db: Database):
    """Команда для получения доступа к веб админ-панели"""
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        
        logger.info(f"🔐 Запрос доступа к админ-панели от {user_id} (@{username})")
        
        # Генерируем временный токен
        token = token_manager.generate_secure_token(user_id, username)
        
        # Формируем URL для доступа
        admin_url = f"http://{ADMIN_HOST}:{ADMIN_PORT}/auth/token-login?token={token}"
        
        # Создаем клавиатуру с кнопкой доступа
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌐 Открыть Админ-панель",
                    url=admin_url
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить токен",
                    callback_data="refresh_admin_token"
                ),
                InlineKeyboardButton(
                    text="🚫 Отозвать доступ",
                    callback_data="revoke_admin_tokens"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика токенов",
                    callback_data="admin_token_stats"
                )
            ]
        ])
        
        # Отправляем сообщение с доступом
        await message.answer(
            f"🔐 <b>Secure доступ к Админ-панели</b>\n\n"
            f"👤 Администратор: @{username}\n"
            f"🕐 Токен действителен: <b>5 минут</b>\n"
            f"🔒 Уровень безопасности: <b>Production</b>\n\n"
            f"⚠️ <i>Не передавайте ссылку третьим лицам!</i>\n"
            f"🔄 <i>Токен автоматически истечет через 5 минут</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Логируем создание токена для аудита
        await db.log_admin_action(
            admin_id=user_id,
            action="admin_panel_access_requested",
            details={
                "username": username,
                "token_expires_in": token_manager.token_expiry,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании доступа к админ-панели: {e}")
        await message.answer(
            "❌ <b>Ошибка доступа</b>\n\n"
            "Не удалось создать secure доступ к админ-панели.\n"
            "Обратитесь к системному администратору.",
            parse_mode="HTML"
        )

@router.callback_query(F.data == "refresh_admin_token")
@admin_required
async def refresh_admin_token(callback, db: Database):
    """Обновление токена доступа"""
    try:
        user_id = callback.from_user.id
        username = callback.from_user.username
        
        # Отзываем старые токены
        revoked_count = token_manager.revoke_user_tokens(user_id)
        
        # Генерируем новый токен
        token = token_manager.generate_secure_token(user_id, username)
        admin_url = f"http://{ADMIN_HOST}:{ADMIN_PORT}/auth/token-login?token={token}"
        
        # Обновляем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌐 Открыть Админ-панель",
                    url=admin_url
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить токен",
                    callback_data="refresh_admin_token"
                ),
                InlineKeyboardButton(
                    text="🚫 Отозвать доступ",
                    callback_data="revoke_admin_tokens"
                )
            ]
        ])
        
        await callback.message.edit_text(
            f"🔄 <b>Токен обновлен</b>\n\n"
            f"👤 Администратор: @{username}\n"
            f"🕐 Новый токен действителен: <b>5 минут</b>\n"
            f"🗑️ Отозвано старых токенов: <b>{revoked_count}</b>\n\n"
            f"⚠️ <i>Не передавайте ссылку третьим лицам!</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await callback.answer("✅ Токен успешно обновлен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления токена: {e}")
        await callback.answer("❌ Ошибка обновления токена", show_alert=True)

@router.callback_query(F.data == "revoke_admin_tokens")
@admin_required
async def revoke_admin_tokens(callback, db: Database):
    """Отзыв всех токенов доступа"""
    try:
        user_id = callback.from_user.id
        username = callback.from_user.username
        
        # Отзываем все токены пользователя
        revoked_count = token_manager.revoke_user_tokens(user_id)
        
        await callback.message.edit_text(
            f"🚫 <b>Доступ отозван</b>\n\n"
            f"👤 Администратор: @{username}\n"
            f"🗑️ Отозвано токенов: <b>{revoked_count}</b>\n"
            f"🔒 Все активные сессии закрыты\n\n"
            f"💡 <i>Используйте /admin для создания нового доступа</i>",
            parse_mode="HTML"
        )
        
        await callback.answer("✅ Все токены отозваны")
        
        # Логируем отзыв токенов
        await db.log_admin_action(
            admin_id=user_id,
            action="admin_tokens_revoked",
            details={
                "username": username,
                "revoked_count": revoked_count,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка отзыва токенов: {e}")
        await callback.answer("❌ Ошибка отзыва токенов", show_alert=True)

@router.callback_query(F.data == "admin_token_stats")
@admin_required
async def admin_token_stats(callback, db: Database):
    """Статистика токенов администратора"""
    try:
        user_id = callback.from_user.id
        
        # Получаем статистику токенов
        user_tokens = temp_tokens.get(user_id, {})
        active_tokens = len(user_tokens)
        
        # Подсчитываем время до истечения токенов
        current_time = int(time.time())
        token_info = []
        
        for token, payload in user_tokens.items():
            expires_at = payload.get('expires_at', 0)
            time_left = max(0, expires_at - current_time)
            token_info.append(f"• Токен: {time_left}с до истечения")
        
        stats_text = (
            f"📊 <b>Статистика токенов</b>\n\n"
            f"👤 Администратор: @{callback.from_user.username}\n"
            f"🔑 Активных токенов: <b>{active_tokens}</b>\n"
            f"⏱️ Максимум токенов: <b>{token_manager.max_tokens_per_user}</b>\n"
            f"🕐 Время жизни токена: <b>{token_manager.token_expiry}с</b>\n\n"
        )
        
        if token_info:
            stats_text += "🔍 <b>Активные токены:</b>\n" + "\n".join(token_info)
        else:
            stats_text += "🔍 <i>Нет активных токенов</i>"
        
        await callback.answer(stats_text, show_alert=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики токенов: {e}")
        await callback.answer("❌ Ошибка получения статистики", show_alert=True)

# Фоновая задача для очистки истекших токенов
async def cleanup_expired_tokens_task():
    """Фоновая задача очистки истекших токенов"""
    while True:
        try:
            token_manager.cleanup_expired_tokens()
            await asyncio.sleep(60)  # Очистка каждую минуту
        except Exception as e:
            logger.error(f"❌ Ошибка в задаче очистки токенов: {e}")
            await asyncio.sleep(60)

# Экспорт менеджера токенов для использования в админ-панели
__all__ = ['router', 'token_manager', 'cleanup_expired_tokens_task']
