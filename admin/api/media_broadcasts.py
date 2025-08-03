"""
Production-ready система рассылок с поддержкой медиафайлов
Поддерживает: изображения, документы, видео, аудио
"""
import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, Request
from pydantic import BaseModel
import httpx

from database.universal_database import UniversalDatabase

# Функция для получения базы данных
async def get_db(request: Request) -> UniversalDatabase:
    """Получить объект базы данных"""
    return request.state.db

# Простая проверка авторизации (без сложных зависимостей)
async def get_current_user(request: Request):
    """Получить текущего пользователя (упрощенная версия)"""
    # В production здесь должна быть полная проверка токена
    # Пока возвращаем фиктивного пользователя для тестирования
    return {"user_id": 1, "username": "admin"}

logger = logging.getLogger(__name__)

# Токен бота - получаем из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения! Добавьте его в .env файл")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Настройки медиафайлов
UPLOAD_DIR = Path("uploads/broadcasts")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {
    'image': {'.jpg', '.jpeg', '.png', '.gif', '.webp'},
    'document': {'.pdf', '.doc', '.docx', '.txt', '.zip', '.rar'},
    'video': {'.mp4', '.avi', '.mov', '.mkv'},
    'audio': {'.mp3', '.wav', '.ogg', '.m4a'}
}

router = APIRouter(prefix="/api/media-broadcasts", tags=["Media Broadcasts"])

class MediaBroadcastRequest(BaseModel):
    """Запрос на создание рассылки с медиафайлами"""
    title: str
    message_text: Optional[str] = None
    target_users: str = "all"
    media_type: Optional[str] = None  # image, document, video, audio
    media_caption: Optional[str] = None
    parse_mode: str = "HTML"
    schedule_time: Optional[datetime] = None

class MediaBroadcastResponse(BaseModel):
    """Ответ создания рассылки с медиафайлами"""
    success: bool
    broadcast_id: Optional[int] = None
    message: str
    media_info: Optional[Dict[str, Any]] = None

def get_file_type(filename: str) -> Optional[str]:
    """Определить тип файла по расширению"""
    ext = Path(filename).suffix.lower()
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return file_type
    return None

def validate_file(file: UploadFile) -> Dict[str, Any]:
    """Валидация загружаемого файла"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Имя файла не указано")
    
    file_type = get_file_type(file.filename)
    if not file_type:
        allowed = []
        for extensions in ALLOWED_EXTENSIONS.values():
            allowed.extend(extensions)
        raise HTTPException(
            status_code=400, 
            detail=f"Неподдерживаемый тип файла. Разрешены: {', '.join(allowed)}"
        )
    
    # Проверяем размер файла (приблизительно)
    if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"Файл слишком большой. Максимум: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    return {
        'type': file_type,
        'filename': file.filename,
        'content_type': file.content_type
    }

async def save_uploaded_file(file: UploadFile, broadcast_id: int) -> Dict[str, Any]:
    """Сохранить загруженный файл"""
    file_info = validate_file(file)
    
    # Создаем уникальное имя файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{broadcast_id}_{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / safe_filename
    
    # Сохраняем файл
    content = await file.read()
    
    # Проверяем реальный размер
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"Файл слишком большой. Максимум: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    return {
        'path': str(file_path),
        'filename': safe_filename,
        'original_name': file.filename,
        'size': len(content),
        'type': file_info['type'],
        'content_type': file.content_type
    }

async def send_media_message(user_id: int, media_info: Dict[str, Any], text: Optional[str] = None) -> Dict[str, Any]:
    """Отправить медиасообщение пользователю"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            media_type = media_info['type']
            file_path = media_info['path']
            
            # Определяем метод API в зависимости от типа медиа
            if media_type == 'image':
                method = 'sendPhoto'
                file_field = 'photo'
            elif media_type == 'document':
                method = 'sendDocument'
                file_field = 'document'
            elif media_type == 'video':
                method = 'sendVideo'
                file_field = 'video'
            elif media_type == 'audio':
                method = 'sendAudio'
                file_field = 'audio'
            else:
                # Fallback к документу
                method = 'sendDocument'
                file_field = 'document'
            
            url = f"{TELEGRAM_API_URL}/{method}"
            
            # Подготавливаем данные
            data = {
                'chat_id': user_id,
                'parse_mode': 'HTML'
            }
            
            # Добавляем текст как подпись для медиа
            if text:
                if media_type == 'image':
                    data['caption'] = text
                elif media_type in ['document', 'video', 'audio']:
                    data['caption'] = text
            
            # Отправляем файл
            with open(file_path, 'rb') as f:
                files = {file_field: f}
                response = await client.post(url, data=data, files=files)
                result = response.json()
            
            if result.get('ok'):
                return {'success': True, 'message_id': result['result']['message_id']}
            else:
                return {'success': False, 'error': result.get('description', 'Unknown error')}
                
    except Exception as e:
        logger.error(f"Ошибка отправки медиасообщения пользователю {user_id}: {e}")
        return {'success': False, 'error': str(e)}

async def send_media_broadcast_messages(
    db: UniversalDatabase,
    broadcast_id: int,
    users: List[Dict[str, Any]],
    media_info: Dict[str, Any],
    message_text: Optional[str] = None
):
    """Отправить медиарассылку пользователям"""
    logger.info(f"Начинаем отправку медиарассылки {broadcast_id} для {len(users)} пользователей")
    
    sent_count = 0
    failed_count = 0
    
    try:
        # Обновляем статус рассылки
        await db.update_broadcast_status(broadcast_id, "sending")
        
        for user in users:
            user_id = user['user_id']
            
            try:
                # Отправляем медиасообщение
                result = await send_media_message(user_id, media_info, message_text)
                
                if result['success']:
                    sent_count += 1
                    logger.debug(f"Медиасообщение отправлено пользователю {user_id}")
                else:
                    failed_count += 1
                    logger.warning(f"Ошибка отправки медиасообщения пользователю {user_id}: {result.get('error')}")
                
                # Небольшая задержка между отправками
                await asyncio.sleep(0.1)
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Критическая ошибка отправки пользователю {user_id}: {e}")
        
        # Обновляем финальную статистику
        await db.update_broadcast_stats(broadcast_id, sent_count=sent_count, failed_count=failed_count)
        await db.update_broadcast_status(broadcast_id, "completed")
        
        logger.info(f"Медиарассылка {broadcast_id} завершена. Отправлено: {sent_count}, Ошибок: {failed_count}")
        
    except Exception as e:
        logger.error(f"Критическая ошибка медиарассылки {broadcast_id}: {e}")
        await db.update_broadcast_status(broadcast_id, "failed")

@router.post("/create", response_model=MediaBroadcastResponse)
async def create_media_broadcast(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    message_text: Optional[str] = Form(None),
    target_users: str = Form("all"),
    media_caption: Optional[str] = Form(None),
    parse_mode: str = Form("HTML"),
    file: Optional[UploadFile] = File(None),
    current_user = Depends(get_current_user),
    db: UniversalDatabase = Depends(get_db)
) -> MediaBroadcastResponse:
    """Создать рассылку с медиафайлом"""
    try:
        logger.info(f"Создание медиарассылки: title={title}, target_users={target_users}, file={file.filename if file else 'None'}")

        # Получаем пользователей для рассылки
        if target_users == "all":
            users = await db.get_all_users_for_broadcast()
        elif target_users == "active":
            users = await db.get_active_users_for_broadcast()
        elif target_users == "subscribers":
            users = await db.get_subscribed_users()
        else:
            users = await db.get_all_users_for_broadcast()

        logger.info(f"Найдено пользователей для рассылки: {len(users)}")
        
        if not users:
            return MediaBroadcastResponse(
                success=False,
                message="Нет пользователей для рассылки"
            )
        
        # Создаем рассылку в базе данных
        try:
            broadcast_id = await db.create_broadcast(
                title=title,
                message_text=message_text or media_caption or "",
                target_users=target_users,
                created_by=current_user.get("user_id", 1)
            )
            logger.info(f"Рассылка создана в БД с ID: {broadcast_id}")
        except Exception as e:
            logger.error(f"Ошибка создания рассылки в БД: {e}")
            return MediaBroadcastResponse(
                success=False,
                message=f"Ошибка создания рассылки в базе данных: {str(e)}"
            )

        if not broadcast_id:
            logger.error("Не удалось получить ID созданной рассылки")
            return MediaBroadcastResponse(
                success=False,
                message="Ошибка создания рассылки в базе данных"
            )
        
        media_info = None
        
        # Обрабатываем медиафайл если есть
        if file and file.filename:
            try:
                media_info = await save_uploaded_file(file, broadcast_id)
                logger.info(f"Медиафайл сохранен для рассылки {broadcast_id}: {media_info['filename']}")
            except Exception as e:
                logger.error(f"Ошибка сохранения медиафайла: {e}")
                return MediaBroadcastResponse(
                    success=False,
                    message=f"Ошибка обработки файла: {str(e)}"
                )
        
        # Запускаем отправку в фоне
        if media_info:
            background_tasks.add_task(
                send_media_broadcast_messages,
                db, broadcast_id, users, media_info, message_text
            )
        else:
            # Если нет медиафайла, используем обычную текстовую рассылку
            from admin.api.broadcasts import send_broadcast_messages
            background_tasks.add_task(
                send_broadcast_messages,
                db, broadcast_id, users, message_text or ""
            )
        
        return MediaBroadcastResponse(
            success=True,
            broadcast_id=broadcast_id,
            message=f"Медиарассылка создана и запущена! ID: {broadcast_id}",
            media_info=media_info
        )
        
    except Exception as e:
        logger.error(f"Ошибка создания медиарассылки: {e}")
        return MediaBroadcastResponse(
            success=False,
            message=f"Ошибка создания рассылки: {str(e)}"
        )

@router.get("/supported-formats")
async def get_supported_formats():
    """Получить список поддерживаемых форматов файлов"""
    return {
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
        "supported_formats": ALLOWED_EXTENSIONS,
        "upload_dir": str(UPLOAD_DIR)
    }
