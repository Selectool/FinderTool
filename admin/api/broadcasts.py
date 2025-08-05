"""
API endpoints для рассылок
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel
import asyncio
import logging

import aiohttp

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from ..auth.permissions import (
        RequireBroadcastCreate, RequireBroadcastSend, log_admin_action
    )
    from ..auth.broadcast_permissions import (
        RequireBroadcastView, RequireBroadcastManage, add_get_user_permissions_method
    )
except ImportError:
    from admin.auth.permissions import (
        RequireBroadcastCreate, RequireBroadcastSend, log_admin_action
    )
    from admin.auth.broadcast_permissions import (
        RequireBroadcastView, RequireBroadcastManage, add_get_user_permissions_method
    )
from database.universal_database import UniversalDatabase

# Инициализируем метод get_user_permissions в классе UniversalDatabase
add_get_user_permissions_method()

router = APIRouter()
logger = logging.getLogger(__name__)

# Токен бота - получаем из переменных окружения
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения! Добавьте его в .env файл")

class BroadcastCreateRequest(BaseModel):
    title: str
    message_text: str
    message_type: str = "text"
    target_type: str = "all"
    send_now: bool = True
    scheduled_time: Optional[str] = None
    send_speed: int = 30
    skip_blocked: bool = True
    save_as_template: bool = False
    parse_mode: str = "HTML"


async def get_db(request: Request) -> UniversalDatabase:
    """Получить объект базы данных"""
    return request.state.db


async def send_telegram_message(user_id: int, text: str, parse_mode: str = "HTML") -> bool:
    """Отправить сообщение пользователю через Telegram Bot API"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": user_id,
        "text": text,
        "parse_mode": parse_mode
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    return True
                else:
                    error_data = await response.json()
                    logger.warning(f"Ошибка отправки сообщения пользователю {user_id}: {error_data}")
                    return False
    except Exception as e:
        logger.error(f"Исключение при отправке сообщения пользователю {user_id}: {e}")
        return False


async def send_broadcast_messages(
    db: UniversalDatabase,
    broadcast_id: int,
    target_users: List[int],
    message_text: str,
    send_speed: int = 30,
    skip_blocked: bool = True,
    parse_mode: str = "HTML"
):
    """Фоновая задача отправки рассылки"""
    logger.info(f"Начинаем отправку рассылки {broadcast_id} для {len(target_users)} пользователей")

    # Обновляем статус рассылки
    await update_broadcast_status(db, broadcast_id, "sending", started_at=datetime.now())

    sent_count = 0
    failed_count = 0

    # Рассчитываем задержку между сообщениями (в секундах)
    delay = 60.0 / send_speed  # send_speed сообщений в минуту

    for user_id in target_users:
        try:
            success = await send_telegram_message(user_id, message_text, parse_mode)

            if success:
                sent_count += 1
                logger.debug(f"Сообщение отправлено пользователю {user_id}")
            else:
                failed_count += 1
                if not skip_blocked:
                    logger.warning(f"Не удалось отправить сообщение пользователю {user_id}")

            # Обновляем счетчики в базе данных каждые 10 сообщений
            if (sent_count + failed_count) % 10 == 0:
                await update_broadcast_counters(db, broadcast_id, sent_count, failed_count)

            # Задержка для соблюдения лимитов
            await asyncio.sleep(delay)

        except Exception as e:
            failed_count += 1
            logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")

    # Финальное обновление статуса
    await update_broadcast_status(
        db, broadcast_id, "completed",
        sent_count=sent_count,
        failed_count=failed_count,
        completed=True
    )

    logger.info(f"Рассылка {broadcast_id} завершена. Отправлено: {sent_count}, Ошибок: {failed_count}")


async def update_broadcast_status(
    db: UniversalDatabase,
    broadcast_id: int,
    status: str,
    sent_count: Optional[int] = None,
    failed_count: Optional[int] = None,
    started_at: Optional[datetime] = None,
    completed: Optional[bool] = None
):
    """Обновить статус рассылки"""
    # Используем универсальный метод базы данных
    await db.update_broadcast_status(broadcast_id, status)


async def update_broadcast_counters(db: UniversalDatabase, broadcast_id: int, sent_count: int, failed_count: int):
    """Обновить счетчики рассылки"""
    # Используем универсальный метод базы данных
    await db.update_broadcast_stats(broadcast_id, sent_count=sent_count, failed_count=failed_count)


@router.post("/")
async def create_broadcast(
    request: BroadcastCreateRequest,
    background_tasks: BackgroundTasks,
    db: UniversalDatabase = Depends(get_db)
) -> Dict[str, Any]:
    """Создать новую рассылку"""
    try:
        # Валидация данных
        if not request.message_text.strip():
            raise HTTPException(status_code=400, detail="Текст сообщения не может быть пустым")

        if len(request.message_text) > 4096:
            raise HTTPException(status_code=400, detail="Текст сообщения слишком длинный (максимум 4096 символов)")

        # Определяем целевую аудиторию
        target_users_list = []

        if request.target_type == "all":
            users = await db.get_all_users_for_broadcast()
            target_users_list = [user["user_id"] for user in users]
        elif request.target_type == "subscribers":
            users = await db.get_subscribed_users()
            target_users_list = [user["user_id"] for user in users]
        elif request.target_type == "active":
            users = await db.get_active_users_for_broadcast(days=30)
            target_users_list = [user["user_id"] for user in users]
        else:
            raise HTTPException(status_code=400, detail="Неверный тип целевой аудитории")

        if not target_users_list:
            raise HTTPException(status_code=400, detail="Не найдено пользователей для рассылки")

        # Создаем рассылку в базе данных
        broadcast_id = await db.create_broadcast(
            title=request.title,
            message_text=request.message_text,
            parse_mode=request.parse_mode,
            target_users=request.target_type,
            created_by=1,  # TODO: получать из текущего пользователя
            scheduled_time=None if request.send_now else request.scheduled_time
        )

        # Если отправляем сейчас, запускаем фоновую задачу
        if request.send_now:
            background_tasks.add_task(
                send_broadcast_messages,
                db,
                broadcast_id,
                target_users_list,
                request.message_text,
                request.send_speed,
                request.skip_blocked,
                request.parse_mode
            )

        return {
            "success": True,
            "broadcast_id": broadcast_id,
            "message": "Рассылка создана успешно" + (" и запущена" if request.send_now else ""),
            "target_count": len(target_users_list),
            "scheduled": not request.send_now
        }

    except Exception as e:
        logger.error(f"Ошибка создания рассылки: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания рассылки: {str(e)}")


@router.post("/{broadcast_id}/send")
@log_admin_action("send_broadcast", "broadcasts")
async def send_broadcast(
    broadcast_id: int,
    background_tasks: BackgroundTasks,
    current_user = Depends(RequireBroadcastSend),
    db: UniversalDatabase = Depends(get_db)
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


async def enhanced_send_broadcast_task(db: UniversalDatabase, broadcast_id: int, broadcast: Dict[str, Any]):
    """Улучшенная фоновая задача отправки рассылки с поддержкой приостановки"""
    try:
        logger.info(f"Начинаем отправку рассылки {broadcast_id}")

        # Получаем список пользователей для рассылки
        target_users = await db.get_broadcast_target_users(broadcast_id)
        total_users = len(target_users)

        if total_users == 0:
            await db.update_broadcast_stats(
                broadcast_id,
                completed=True,
                error_message="Нет пользователей для отправки"
            )
            await db.update_broadcast_status(broadcast_id, "completed")
            return

        sent_count = 0
        failed_count = 0
        blocked_count = 0
        start_time = datetime.now()

        # Настройки скорости отправки
        send_rate = broadcast.get("send_rate", "normal")
        delay_map = {
            "slow": 6.0,    # 10 сообщений/мин
            "normal": 2.0,  # 30 сообщений/мин
            "fast": 1.0     # 60 сообщений/мин
        }
        delay = delay_map.get(send_rate, 2.0)

        # Отправляем сообщения с проверкой статуса
        for i, user_id in enumerate(target_users):
            try:
                # Проверяем статус рассылки (может быть приостановлена)
                current_broadcast = await db.get_broadcast_by_id(broadcast_id)
                if current_broadcast["status"] == "paused":
                    logger.info(f"Рассылка {broadcast_id} приостановлена")
                    return
                elif current_broadcast["status"] == "stopped":
                    logger.info(f"Рассылка {broadcast_id} остановлена")
                    return

                # Отправляем сообщение
                success = await send_message_to_user(
                    user_id,
                    broadcast["message_text"],
                    broadcast.get("parse_mode", "HTML")
                )

                if success:
                    sent_count += 1
                    await db.log_broadcast_delivery(broadcast_id, user_id, "sent", "Успешно доставлено")
                else:
                    failed_count += 1
                    await db.log_broadcast_delivery(broadcast_id, user_id, "failed", "Ошибка доставки")

                # Обновляем статистику каждые 10 сообщений
                if (i + 1) % 10 == 0:
                    await db.update_broadcast_stats(
                        broadcast_id,
                        sent_count=sent_count,
                        failed_count=failed_count
                    )

                    # Логируем прогресс
                    progress = (i + 1) / total_users * 100
                    logger.info(f"Рассылка {broadcast_id}: прогресс {progress:.1f}% ({i + 1}/{total_users})")

                # Пауза между отправками
                await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")

                # Определяем тип ошибки
                error_str = str(e).lower()
                if "blocked" in error_str or "bot was blocked" in error_str:
                    blocked_count += 1
                    await db.log_broadcast_delivery(broadcast_id, user_id, "blocked", "Пользователь заблокировал бота")
                else:
                    failed_count += 1
                    await db.log_broadcast_delivery(broadcast_id, user_id, "failed", str(e))

        # Финальное обновление статистики
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        await db.update_broadcast_stats(
            broadcast_id,
            sent_count=sent_count,
            failed_count=failed_count,
            completed=True
        )

        await db.update_broadcast_status(broadcast_id, "completed")

        logger.info(f"Рассылка {broadcast_id} завершена: отправлено {sent_count}, ошибок {failed_count}, заблокировано {blocked_count}, время {duration:.1f}с")

    except Exception as e:
        logger.error(f"Критическая ошибка в рассылке {broadcast_id}: {e}")
        await db.update_broadcast_stats(
            broadcast_id,
            completed=True,
            error_message=str(e)
        )
        await db.update_broadcast_status(broadcast_id, "failed")


# Оставляем старую функцию для совместимости
async def send_broadcast_task(db: UniversalDatabase, broadcast_id: int, broadcast: Dict[str, Any]):
    """Фоновая задача отправки рассылки (устаревшая версия)"""
    await enhanced_send_broadcast_task(db, broadcast_id, broadcast)


@router.post("/{broadcast_id}/start")
@log_admin_action("start_broadcast", "broadcasts")
async def start_broadcast(
    broadcast_id: int,
    background_tasks: BackgroundTasks,
    current_user = Depends(RequireBroadcastSend),
    db: UniversalDatabase = Depends(get_db)
) -> Dict[str, Any]:
    """Запустить рассылку"""

    broadcast = await db.get_broadcast_by_id(broadcast_id)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    if broadcast["status"] != "pending":
        raise HTTPException(status_code=400, detail="Рассылку можно запустить только в статусе 'pending'")

    # Обновляем статус
    await db.update_broadcast_stats(
        broadcast_id,
        started_at=datetime.now()
    )
    await db.update_broadcast_status(broadcast_id, "sending")

    # Запускаем отправку в фоне с новым сервисом
    from ..services.broadcast_sender import enhanced_send_broadcast_task_with_sender
    background_tasks.add_task(enhanced_send_broadcast_task_with_sender, db, broadcast_id, broadcast)

    return {
        "message": "Рассылка запущена",
        "broadcast_id": broadcast_id,
        "status": "sending"
    }


@router.post("/{broadcast_id}/pause")
@log_admin_action("pause_broadcast", "broadcasts")
async def pause_broadcast(
    broadcast_id: int,
    current_user = Depends(RequireBroadcastSend),
    db: UniversalDatabase = Depends(get_db)
) -> Dict[str, Any]:
    """Приостановить рассылку"""

    broadcast = await db.get_broadcast_by_id(broadcast_id)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    if broadcast["status"] != "sending":
        raise HTTPException(status_code=400, detail="Можно приостановить только активную рассылку")

    await db.update_broadcast_status(broadcast_id, "paused")

    return {
        "message": "Рассылка приостановлена",
        "broadcast_id": broadcast_id,
        "status": "paused"
    }


@router.post("/{broadcast_id}/resume")
@log_admin_action("resume_broadcast", "broadcasts")
async def resume_broadcast(
    broadcast_id: int,
    background_tasks: BackgroundTasks,
    current_user = Depends(RequireBroadcastSend),
    db: UniversalDatabase = Depends(get_db)
) -> Dict[str, Any]:
    """Возобновить рассылку"""

    broadcast = await db.get_broadcast_by_id(broadcast_id)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    if broadcast["status"] != "paused":
        raise HTTPException(status_code=400, detail="Можно возобновить только приостановленную рассылку")

    await db.update_broadcast_status(broadcast_id, "sending")

    # Возобновляем отправку в фоне с новым сервисом
    from ..services.broadcast_sender import enhanced_send_broadcast_task_with_sender
    background_tasks.add_task(enhanced_send_broadcast_task_with_sender, db, broadcast_id, broadcast)

    return {
        "message": "Рассылка возобновлена",
        "broadcast_id": broadcast_id,
        "status": "sending"
    }


@router.post("/{broadcast_id}/stop")
@log_admin_action("stop_broadcast", "broadcasts")
async def stop_broadcast(
    broadcast_id: int,
    current_user = Depends(RequireBroadcastSend),
    db: UniversalDatabase = Depends(get_db)
) -> Dict[str, Any]:
    """Остановить рассылку"""

    broadcast = await db.get_broadcast_by_id(broadcast_id)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    if broadcast["status"] not in ["sending", "paused"]:
        raise HTTPException(status_code=400, detail="Можно остановить только активную или приостановленную рассылку")

    await db.update_broadcast_stats(
        broadcast_id,
        completed=True,
        error_message="Остановлена администратором"
    )
    await db.update_broadcast_status(broadcast_id, "stopped")

    return {
        "message": "Рассылка остановлена",
        "broadcast_id": broadcast_id,
        "status": "stopped"
    }


@router.get("/{broadcast_id}/stats")
async def get_broadcast_stats(
    broadcast_id: int,
    current_user = Depends(RequireBroadcastView),
    db: UniversalDatabase = Depends(get_db)
) -> Dict[str, Any]:
    """Получить статистику рассылки в реальном времени"""

    broadcast = await db.get_broadcast_by_id(broadcast_id)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    stats = await db.get_broadcast_detailed_stats(broadcast_id)

    return {
        "broadcast_id": broadcast_id,
        "status": broadcast["status"],
        "sent_count": broadcast["sent_count"] or 0,
        "failed_count": broadcast["failed_count"] or 0,
        "delivered": stats.get("delivered", 0),
        "blocked": stats.get("blocked", 0),
        "total_recipients": stats.get("total_recipients", 0),
        "current_rate": stats.get("current_rate", 0),
        "estimated_time": stats.get("estimated_time", ""),
        "started_at": broadcast["started_at"],
        "updated_at": datetime.now()
    }








@router.get("/{broadcast_id}/logs")
async def get_broadcast_logs(
    broadcast_id: int,
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
    current_user = Depends(RequireBroadcastView),
    db: UniversalDatabase = Depends(get_db)
) -> Dict[str, Any]:
    """Получить логи рассылки"""

    broadcast = await db.get_broadcast_by_id(broadcast_id)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    logs_data = await db.get_broadcast_logs(broadcast_id, page, per_page, status)

    return {
        "broadcast_id": broadcast_id,
        "logs": logs_data["logs"],
        "pagination": {
            "total": logs_data["total"],
            "page": logs_data["page"],
            "per_page": logs_data["per_page"],
            "pages": logs_data["pages"]
        }
    }


@router.get("/{broadcast_id}/logs/export")
async def export_broadcast_logs(
    broadcast_id: int,
    current_user = Depends(RequireBroadcastView),
    db: UniversalDatabase = Depends(get_db)
):
    """Экспортировать логи рассылки в CSV"""

    broadcast = await db.get_broadcast_by_id(broadcast_id)
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    logs = await db.get_all_broadcast_logs(broadcast_id)

    # Создаем CSV
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Заголовки
    writer.writerow([
        'Время', 'Пользователь ID', 'Статус', 'Сообщение', 'Детали ошибки'
    ])

    # Данные
    for log in logs:
        writer.writerow([
            log['created_at'],
            log['user_id'],
            log['status'],
            log['message'],
            log.get('error_details', '')
        ])

    output.seek(0)

    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type='text/csv',
        headers={
            "Content-Disposition": f"attachment; filename=broadcast_{broadcast_id}_logs.csv"
        }
    )


@router.get("/audience-count")
async def get_audience_count(
    target: str = "all",
    current_user = Depends(RequireBroadcastView),
    db: UniversalDatabase = Depends(get_db)
) -> Dict[str, Any]:
    """Получить количество пользователей в целевой аудитории"""

    count = await db.get_target_audience_count(target)

    return {
        "target": target,
        "count": count
    }


async def send_message_to_user(user_id: int, message_text: str, parse_mode: str = "HTML") -> bool:
    """Отправить сообщение пользователю через Telegram Bot API"""
    try:
        from ..services.broadcast_sender import send_message_to_user as sender_func
        return await sender_func(user_id, message_text, parse_mode)

    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
        return False


@router.get("/test")
async def test_endpoint():
    """Тестовый endpoint без авторизации"""
    return {"status": "ok", "message": "Test endpoint works"}


@router.get("/audience-stats-public")
async def get_audience_stats_public(
    target_type: str = "all",
    db: UniversalDatabase = Depends(get_db)
):
    """Получить детальную статистику аудитории для рассылки (без авторизации)"""
    try:
        # Получаем общую статистику
        total_users = await db.get_users_count()
        active_users = await db.get_active_users_count()
        subscribers = await db.get_subscribers_count()
        blocked_users = await db.get_blocked_users_count()

        # Определяем количество получателей в зависимости от типа
        if target_type == "all":
            recipients = total_users
        elif target_type == "active":
            recipients = active_users
        elif target_type == "subscribers":
            recipients = subscribers
        else:
            recipients = total_users

        # Рассчитываем примерное время отправки (30 сообщений в минуту по умолчанию)
        estimated_minutes = max(1, recipients // 30)
        if estimated_minutes < 60:
            estimated_time = f"{estimated_minutes} мин"
        else:
            hours = estimated_minutes // 60
            minutes = estimated_minutes % 60
            estimated_time = f"{hours}ч {minutes}м" if minutes > 0 else f"{hours}ч"

        return {
            "recipients": recipients,
            "estimated_time": estimated_time,
            "details": {
                "total_users": total_users,
                "active_users": active_users,
                "subscribers": subscribers,
                "blocked_users": blocked_users
            }
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики аудитории: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения данных")


@router.get("/audience-stats")
async def get_audience_stats(
    target_type: str = "all",
    db: UniversalDatabase = Depends(get_db)
):
    """Получить детальную статистику аудитории для рассылки"""
    try:
        # Получаем общую статистику
        total_users = await db.get_users_count()
        active_users = await db.get_active_users_count()
        subscribers = await db.get_subscribers_count()
        blocked_users = await db.get_blocked_users_count()

        # Определяем количество получателей в зависимости от типа
        if target_type == "all":
            recipients = total_users
        elif target_type == "active":
            recipients = active_users
        elif target_type == "subscribers":
            recipients = subscribers
        else:
            recipients = total_users

        # Рассчитываем примерное время отправки (30 сообщений в минуту по умолчанию)
        estimated_minutes = max(1, recipients // 30)
        if estimated_minutes < 60:
            estimated_time = f"{estimated_minutes} мин"
        else:
            hours = estimated_minutes // 60
            minutes = estimated_minutes % 60
            estimated_time = f"{hours}ч {minutes}м" if minutes > 0 else f"{hours}ч"

        return {
            "recipients": recipients,
            "estimated_time": estimated_time,
            "details": {
                "total_users": total_users,
                "active_users": active_users,
                "subscribers": subscribers,
                "blocked_users": blocked_users
            }
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики аудитории: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения данных")


@router.get("/recipients-preview")
async def get_recipients_preview(
    target_type: str = "all",
    limit: int = 50,
    db: UniversalDatabase = Depends(get_db)
):
    """Получить предпросмотр списка получателей"""
    try:
        # Получаем пользователей в зависимости от типа аудитории
        if target_type == "all":
            users = await db.get_all_users(limit=limit)
            total = await db.get_users_count()
        elif target_type == "active":
            users = await db.get_active_users(limit=limit)
            total = await db.get_active_users_count()
        elif target_type == "subscribers":
            users = await db.get_subscribers(limit=limit)
            total = await db.get_subscribers_count()
        else:
            users = await db.get_all_users(limit=limit)
            total = await db.get_users_count()

        # Форматируем результат
        recipients_list = []
        for user in users:
            recipients_list.append({
                "user_id": user.get('user_id', 0),
                "first_name": user.get('first_name', ''),
                "last_name": user.get('last_name', ''),
                "username": user.get('username', ''),
                "created_at": user.get('created_at', '')
            })

        return {
            "recipients": recipients_list,
            "total": total,
            "showing": len(recipients_list)
        }
    except Exception as e:
        logger.error(f"Ошибка получения предпросмотра получателей: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения данных")
