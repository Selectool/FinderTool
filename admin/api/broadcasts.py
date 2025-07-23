"""
API endpoints для рассылок
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import logging

from ..auth.permissions import RequireBroadcastCreate, RequireBroadcastSend, log_admin_action
from database.models import Database

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_db(request: Request) -> Database:
    """Получить объект базы данных"""
    return request.state.db


@router.post("/")
@log_admin_action("create_broadcast", "broadcasts")
async def create_broadcast(
    message_text: str,
    target_type: str = "all",  # all, subscribers, active, custom
    target_users: Optional[List[int]] = None,
    schedule_time: Optional[datetime] = None,
    current_user = Depends(RequireBroadcastCreate),
    db: Database = Depends(get_db)
) -> Dict[str, Any]:
    """Создать новую рассылку"""

    # Валидация данных
    if not message_text.strip():
        raise HTTPException(status_code=400, detail="Текст сообщения не может быть пустым")

    if len(message_text) > 4096:
        raise HTTPException(status_code=400, detail="Текст сообщения слишком длинный (максимум 4096 символов)")

    # Определяем целевую аудиторию
    target_users_list = []

    if target_type == "all":
        users = await db.get_all_users()
        target_users_list = [user["user_id"] for user in users]
    elif target_type == "subscribers":
        users = await db.get_subscribed_users()
        target_users_list = [user["user_id"] for user in users]
    elif target_type == "active":
        users = await db.get_active_users(days=30)
        target_users_list = [user["user_id"] for user in users]
    elif target_type == "custom" and target_users:
        target_users_list = target_users
    else:
        raise HTTPException(status_code=400, detail="Неверный тип целевой аудитории")

    if not target_users_list:
        raise HTTPException(status_code=400, detail="Не найдено пользователей для рассылки")

    # Создаем рассылку в базе данных
    broadcast_id = await db.create_broadcast(
        message_text=message_text,
        target_users=target_users_list,
        created_by=current_user.user_id,
        schedule_time=schedule_time
    )

    return {
        "broadcast_id": broadcast_id,
        "message": "Рассылка создана успешно",
        "target_count": len(target_users_list),
        "scheduled": schedule_time is not None
    }


@router.post("/{broadcast_id}/send")
@log_admin_action("send_broadcast", "broadcasts")
async def send_broadcast(
    broadcast_id: int,
    background_tasks: BackgroundTasks,
    current_user = Depends(RequireBroadcastSend),
    db: Database = Depends(get_db)
) -> Dict[str, Any]:
    """Отправить рассылку"""

    # Получаем информацию о рассылке
    broadcast = await db.get_broadcast_by_id(broadcast_id)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    if broadcast["status"] == "sent":
        raise HTTPException(status_code=400, detail="Рассылка уже отправлена")

    if broadcast["status"] == "sending":
        raise HTTPException(status_code=400, detail="Рассылка уже отправляется")

    # Обновляем статус рассылки
    await db.update_broadcast_status(broadcast_id, "sending")

    # Запускаем отправку в фоне
    background_tasks.add_task(send_broadcast_task, db, broadcast_id, broadcast)

    return {
        "message": "Рассылка запущена",
        "broadcast_id": broadcast_id,
        "status": "sending"
    }


async def send_broadcast_task(db: Database, broadcast_id: int, broadcast: Dict[str, Any]):
    """Фоновая задача отправки рассылки"""
    try:
        logger.info(f"Начинаем отправку рассылки {broadcast_id}")

        # Получаем список пользователей для рассылки
        target_users = await db.get_broadcast_target_users(broadcast_id)

        sent_count = 0
        failed_count = 0

        # Отправляем сообщения с интервалами для избежания флуда
        for user_id in target_users:
            try:
                # Здесь должна быть интеграция с Telegram Bot API
                # Пока что имитируем отправку
                success = await send_message_to_user(user_id, broadcast["message_text"])

                if success:
                    sent_count += 1
                    await db.log_broadcast_delivery(broadcast_id, user_id, "sent")
                else:
                    failed_count += 1
                    await db.log_broadcast_delivery(broadcast_id, user_id, "failed")

                # Пауза между отправками (защита от флуда)
                await asyncio.sleep(0.1)  # 100ms между сообщениями

            except Exception as e:
                logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
                failed_count += 1
                await db.log_broadcast_delivery(broadcast_id, user_id, "failed", str(e))

        # Обновляем статистику рассылки
        await db.update_broadcast_stats(broadcast_id, sent_count, failed_count)
        await db.update_broadcast_status(broadcast_id, "completed")

        logger.info(f"Рассылка {broadcast_id} завершена. Отправлено: {sent_count}, Ошибок: {failed_count}")

    except Exception as e:
        logger.error(f"Критическая ошибка при отправке рассылки {broadcast_id}: {e}")
        await db.update_broadcast_status(broadcast_id, "failed")


async def send_message_to_user(user_id: int, message_text: str) -> bool:
    """Отправить сообщение пользователю через Telegram Bot API"""
    try:
        # TODO: Интеграция с основным ботом для отправки сообщений
        # Пока что имитируем успешную отправку
        await asyncio.sleep(0.01)  # Имитация сетевого запроса
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
        return False
