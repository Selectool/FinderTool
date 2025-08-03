"""
API endpoint для webhook уведомлений от ЮKassa
"""
import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse

from database.universal_database import UniversalDatabase
from services.yookassa_webhook import create_webhook_handler
from config import YOOKASSA_MODE

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_database_instance():
    """Dependency для получения экземпляра базы данных"""
    db = UniversalDatabase()
    await db.init_db()
    return db


@router.post("/yookassa/webhook")
async def yookassa_webhook(request: Request, db: UniversalDatabase = Depends(get_database_instance)):
    """
    Endpoint для обработки webhook уведомлений от ЮKassa
    """
    try:
        # Получаем тело запроса
        body = await request.body()
        payload = body.decode('utf-8')
        
        # Получаем заголовки
        headers = dict(request.headers)
        signature = headers.get('x-yookassa-signature', '')
        
        logger.info(f"📨 Получен webhook от ЮKassa:")
        logger.info(f"  - Режим: {YOOKASSA_MODE}")
        logger.info(f"  - Размер payload: {len(payload)} байт")
        logger.info(f"  - Подпись: {signature[:20]}..." if signature else "  - Подпись отсутствует")
        
        # Парсим JSON
        import json
        try:
            notification_data = json.loads(payload)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")
        
        # Создаем обработчик webhook'ов
        webhook_handler = create_webhook_handler(db=db)
        
        # Проверяем подпись (если настроена)
        if signature and not webhook_handler.verify_signature(payload, signature):
            logger.error("❌ Неверная подпись webhook уведомления")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Обрабатываем уведомление
        success = await webhook_handler.handle_payment_notification(notification_data)
        
        if success:
            logger.info("✅ Webhook уведомление обработано успешно")
            return JSONResponse(
                status_code=200,
                content={"status": "success", "message": "Webhook processed successfully"}
            )
        else:
            logger.error("❌ Ошибка при обработке webhook уведомления")
            raise HTTPException(status_code=500, detail="Webhook processing failed")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при обработке webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/yookassa/webhook/test")
async def test_webhook_endpoint():
    """
    Тестовый endpoint для проверки доступности webhook'а
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "message": "ЮKassa webhook endpoint is working",
            "mode": YOOKASSA_MODE,
            "timestamp": "2025-07-27T17:52:00Z"
        }
    )


@router.post("/yookassa/webhook/test")
async def test_webhook_processing(request: Request, db: UniversalDatabase = Depends(get_database_instance)):
    """
    Тестовый endpoint для проверки обработки webhook уведомлений
    """
    try:
        body = await request.body()
        payload = body.decode('utf-8')
        
        import json
        notification_data = json.loads(payload)
        
        logger.info(f"🧪 Тестовая обработка webhook уведомления")
        
        # Создаем обработчик webhook'ов
        webhook_handler = create_webhook_handler(db=db)
        
        # Обрабатываем уведомление
        success = await webhook_handler.handle_payment_notification(notification_data)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success" if success else "error",
                "message": "Test webhook processed",
                "processed": success
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при тестовой обработке webhook: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e)
            }
        )
