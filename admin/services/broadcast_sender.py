"""
Сервис для отправки рассылок через Telegram Bot API
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import FSInputFile

from config import BOT_TOKEN
from database.universal_database import UniversalDatabase
from bot.utils.error_handler import safe_send_message

logger = logging.getLogger(__name__)


class BroadcastSender:
    """Класс для отправки рассылок"""
    
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.db = UniversalDatabase()
    
    async def send_message_to_user(
        self, 
        user_id: int, 
        message_text: str, 
        parse_mode: str = "HTML",
        media_file: Optional[str] = None,
        message_type: str = "text"
    ) -> Dict[str, Any]:
        """
        Отправить сообщение пользователю
        
        Returns:
            Dict с результатом: {"success": bool, "error": str, "status": str}
        """
        try:
            if message_type == "text":
                # Обычное текстовое сообщение
                success = await safe_send_message(
                    bot=self.bot,
                    user_id=user_id,
                    text=message_text,
                    db=self.db,
                    parse_mode=parse_mode
                )
                
                if success:
                    return {"success": True, "error": "", "status": "sent"}
                else:
                    return {"success": False, "error": "Ошибка отправки", "status": "failed"}
            
            elif message_type == "photo" and media_file:
                # Сообщение с изображением
                try:
                    photo = FSInputFile(media_file)
                    await self.bot.send_photo(
                        chat_id=user_id,
                        photo=photo,
                        caption=message_text,
                        parse_mode=parse_mode
                    )
                    return {"success": True, "error": "", "status": "sent"}
                    
                except Exception as e:
                    logger.error(f"Ошибка отправки фото пользователю {user_id}: {e}")
                    return {"success": False, "error": str(e), "status": "failed"}
            
            elif message_type == "document" and media_file:
                # Сообщение с документом
                try:
                    document = FSInputFile(media_file)
                    await self.bot.send_document(
                        chat_id=user_id,
                        document=document,
                        caption=message_text,
                        parse_mode=parse_mode
                    )
                    return {"success": True, "error": "", "status": "sent"}
                    
                except Exception as e:
                    logger.error(f"Ошибка отправки документа пользователю {user_id}: {e}")
                    return {"success": False, "error": str(e), "status": "failed"}
            
            else:
                return {"success": False, "error": "Неподдерживаемый тип сообщения", "status": "failed"}
                
        except TelegramForbiddenError as e:
            # Пользователь заблокировал бота
            logger.info(f"Пользователь {user_id} заблокировал бота")
            
            # Обновляем статус в БД
            await self.db.update_user_bot_blocked_status(user_id, True)
            
            return {"success": False, "error": "Пользователь заблокировал бота", "status": "blocked"}
            
        except TelegramBadRequest as e:
            # Неверный запрос (например, неверный user_id)
            error_msg = str(e)
            logger.warning(f"Неверный запрос для пользователя {user_id}: {error_msg}")
            
            if "chat not found" in error_msg.lower():
                return {"success": False, "error": "Чат не найден", "status": "not_found"}
            else:
                return {"success": False, "error": error_msg, "status": "failed"}
                
        except TelegramRetryAfter as e:
            # Превышен лимит запросов
            retry_after = e.retry_after
            logger.warning(f"Превышен лимит запросов, повтор через {retry_after} секунд")
            
            # Ждем указанное время
            await asyncio.sleep(retry_after)
            
            # Повторяем попытку
            return await self.send_message_to_user(user_id, message_text, parse_mode, media_file, message_type)
            
        except Exception as e:
            # Другие ошибки
            logger.error(f"Неожиданная ошибка при отправке сообщения пользователю {user_id}: {e}")
            return {"success": False, "error": str(e), "status": "failed"}
    
    async def send_broadcast_batch(
        self,
        broadcast_id: int,
        user_ids: list,
        message_text: str,
        parse_mode: str = "HTML",
        media_file: Optional[str] = None,
        message_type: str = "text",
        delay: float = 1.0
    ) -> Dict[str, int]:
        """
        Отправить рассылку группе пользователей
        
        Returns:
            Dict со статистикой: {"sent": int, "failed": int, "blocked": int}
        """
        stats = {"sent": 0, "failed": 0, "blocked": 0, "not_found": 0}
        
        for user_id in user_ids:
            try:
                # Проверяем статус рассылки (может быть приостановлена)
                broadcast = await self.db.get_broadcast_by_id(broadcast_id)
                if broadcast["status"] in ["paused", "stopped"]:
                    logger.info(f"Рассылка {broadcast_id} приостановлена/остановлена")
                    break
                
                # Отправляем сообщение
                result = await self.send_message_to_user(
                    user_id, message_text, parse_mode, media_file, message_type
                )
                
                # Обновляем статистику
                status = result["status"]
                if status == "sent":
                    stats["sent"] += 1
                elif status == "blocked":
                    stats["blocked"] += 1
                elif status == "not_found":
                    stats["not_found"] += 1
                else:
                    stats["failed"] += 1
                
                # Логируем результат
                await self.db.log_broadcast_delivery(
                    broadcast_id=broadcast_id,
                    user_id=user_id,
                    status=status,
                    message=result.get("error", ""),
                    error_details=result.get("error", "")
                )
                
                # Пауза между отправками
                await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(f"Ошибка в batch отправке для пользователя {user_id}: {e}")
                stats["failed"] += 1
                
                await self.db.log_broadcast_delivery(
                    broadcast_id=broadcast_id,
                    user_id=user_id,
                    status="failed",
                    message="Критическая ошибка",
                    error_details=str(e)
                )
        
        return stats
    
    async def test_message_send(self, user_id: int, message_text: str) -> bool:
        """Тестовая отправка сообщения"""
        result = await self.send_message_to_user(user_id, message_text)
        return result["success"]
    
    async def close(self):
        """Закрыть соединение с ботом"""
        await self.bot.session.close()


# Глобальный экземпляр отправителя
_broadcast_sender = None


async def get_broadcast_sender() -> BroadcastSender:
    """Получить экземпляр отправителя рассылок"""
    global _broadcast_sender
    
    if _broadcast_sender is None:
        _broadcast_sender = BroadcastSender()
    
    return _broadcast_sender


async def send_message_to_user(
    user_id: int, 
    message_text: str, 
    parse_mode: str = "HTML",
    media_file: Optional[str] = None,
    message_type: str = "text"
) -> bool:
    """
    Упрощенная функция для отправки сообщения пользователю
    Используется в API endpoints для обратной совместимости
    """
    sender = await get_broadcast_sender()
    result = await sender.send_message_to_user(
        user_id, message_text, parse_mode, media_file, message_type
    )
    return result["success"]


async def cleanup_broadcast_sender():
    """Очистить ресурсы отправителя"""
    global _broadcast_sender
    
    if _broadcast_sender:
        await _broadcast_sender.close()
        _broadcast_sender = None


# Функция для интеграции с существующим кодом
async def enhanced_send_broadcast_task_with_sender(
    db: UniversalDatabase, 
    broadcast_id: int, 
    broadcast: Dict[str, Any]
):
    """
    Улучшенная задача отправки рассылки с использованием BroadcastSender
    """
    sender = await get_broadcast_sender()
    
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

        # Настройки скорости отправки
        send_rate = broadcast.get("send_rate", "normal")
        delay_map = {
            "slow": 6.0,    # 10 сообщений/мин
            "normal": 2.0,  # 30 сообщений/мин  
            "fast": 1.0     # 60 сообщений/мин
        }
        delay = delay_map.get(send_rate, 2.0)

        # Отправляем рассылку батчами по 50 пользователей
        batch_size = 50
        total_stats = {"sent": 0, "failed": 0, "blocked": 0, "not_found": 0}
        
        for i in range(0, total_users, batch_size):
            batch_users = target_users[i:i + batch_size]
            
            # Отправляем батч
            batch_stats = await sender.send_broadcast_batch(
                broadcast_id=broadcast_id,
                user_ids=batch_users,
                message_text=broadcast["message_text"],
                parse_mode=broadcast.get("parse_mode", "HTML"),
                media_file=broadcast.get("media_file"),
                message_type=broadcast.get("message_type", "text"),
                delay=delay
            )
            
            # Обновляем общую статистику
            for key in total_stats:
                total_stats[key] += batch_stats[key]
            
            # Обновляем статистику в БД
            await db.update_broadcast_stats(
                broadcast_id, 
                sent_count=total_stats["sent"], 
                failed_count=total_stats["failed"] + total_stats["not_found"]
            )
            
            # Логируем прогресс
            progress = min(i + batch_size, total_users) / total_users * 100
            logger.info(f"Рассылка {broadcast_id}: прогресс {progress:.1f}% ({min(i + batch_size, total_users)}/{total_users})")

        # Финальное обновление
        await db.update_broadcast_stats(
            broadcast_id, 
            sent_count=total_stats["sent"], 
            failed_count=total_stats["failed"] + total_stats["not_found"],
            completed=True
        )
        
        await db.update_broadcast_status(broadcast_id, "completed")
        
        logger.info(f"Рассылка {broadcast_id} завершена: отправлено {total_stats['sent']}, ошибок {total_stats['failed']}, заблокировано {total_stats['blocked']}")

    except Exception as e:
        logger.error(f"Критическая ошибка в рассылке {broadcast_id}: {e}")
        await db.update_broadcast_stats(
            broadcast_id, 
            completed=True,
            error_message=str(e)
        )
        await db.update_broadcast_status(broadcast_id, "failed")
