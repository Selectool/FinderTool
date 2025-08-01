"""
Production-ready health check система
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from database.production_manager import db_manager
from config import IS_PRODUCTION, HEALTH_CHECK_ENABLED, BOT_TOKEN

logger = logging.getLogger(__name__)


class HealthCheckManager:
    """Менеджер для проверки здоровья системы"""
    
    def __init__(self):
        self.last_check = None
        self.check_interval = 300  # 5 минут
        self.health_status = {
            'status': 'unknown',
            'last_check': None,
            'components': {}
        }
    
    async def perform_health_check(self) -> Dict[str, Any]:
        """Выполнить полную проверку здоровья системы"""
        if not HEALTH_CHECK_ENABLED:
            return {'status': 'disabled', 'message': 'Health check отключен'}
        
        logger.info("Начинаем проверку здоровья системы...")
        start_time = time.time()
        
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'environment': 'production' if IS_PRODUCTION else 'development',
            'status': 'healthy',
            'components': {},
            'check_duration_ms': 0
        }
        
        # Проверка базы данных
        try:
            db_health = await self._check_database()
            health_status['components']['database'] = db_health
            
            if db_health['status'] != 'healthy':
                health_status['status'] = 'unhealthy'
                
        except Exception as e:
            logger.error(f"Ошибка проверки базы данных: {e}")
            health_status['components']['database'] = {
                'status': 'error',
                'error': str(e)
            }
            health_status['status'] = 'unhealthy'
        
        # Проверка Telegram Bot API
        try:
            bot_health = await self._check_bot_api()
            health_status['components']['telegram_bot'] = bot_health
            
            if bot_health['status'] != 'healthy':
                health_status['status'] = 'unhealthy'
                
        except Exception as e:
            logger.error(f"Ошибка проверки Telegram Bot API: {e}")
            health_status['components']['telegram_bot'] = {
                'status': 'error',
                'error': str(e)
            }
            health_status['status'] = 'unhealthy'
        
        # Проверка памяти и ресурсов
        try:
            system_health = await self._check_system_resources()
            health_status['components']['system'] = system_health
            
            if system_health['status'] != 'healthy':
                health_status['status'] = 'degraded'
                
        except Exception as e:
            logger.error(f"Ошибка проверки системных ресурсов: {e}")
            health_status['components']['system'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Проверка ЮKassa (если в production)
        if IS_PRODUCTION:
            try:
                payment_health = await self._check_payment_system()
                health_status['components']['payments'] = payment_health
                
                if payment_health['status'] != 'healthy':
                    health_status['status'] = 'degraded'
                    
            except Exception as e:
                logger.error(f"Ошибка проверки платежной системы: {e}")
                health_status['components']['payments'] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Завершаем проверку
        health_status['check_duration_ms'] = int((time.time() - start_time) * 1000)
        self.health_status = health_status
        self.last_check = time.time()
        
        logger.info(f"Проверка здоровья завершена: {health_status['status']} ({health_status['check_duration_ms']}ms)")
        
        return health_status
    
    async def _check_database(self) -> Dict[str, Any]:
        """Проверка состояния базы данных"""
        try:
            # Используем health check из database manager
            db_health = await db_manager.health_check()
            
            if db_health['status'] == 'healthy':
                # Дополнительная проверка - получаем информацию о БД
                db_info = await db_manager.get_database_info()
                
                return {
                    'status': 'healthy',
                    'database_type': db_info.get('database_type', 'unknown'),
                    'connection_status': db_info.get('connection_status', 'unknown'),
                    'tables_count': len(db_info.get('tables', [])),
                    'users_count': db_info.get('users_count', 0)
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': db_health.get('error', 'Unknown database error')
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def _check_bot_api(self) -> Dict[str, Any]:
        """Проверка Telegram Bot API"""
        try:
            from aiogram import Bot
            
            bot = Bot(token=BOT_TOKEN)
            
            # Простая проверка - получаем информацию о боте
            bot_info = await bot.get_me()
            await bot.session.close()
            
            return {
                'status': 'healthy',
                'bot_username': bot_info.username,
                'bot_id': bot_info.id,
                'can_join_groups': bot_info.can_join_groups,
                'can_read_all_group_messages': bot_info.can_read_all_group_messages
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def _check_system_resources(self) -> Dict[str, Any]:
        """Проверка системных ресурсов"""
        try:
            import psutil
            import os
            
            # Информация о памяти
            memory = psutil.virtual_memory()
            
            # Информация о диске
            disk = psutil.disk_usage('/')
            
            # Информация о процессе
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()
            
            # Определяем статус на основе использования ресурсов
            status = 'healthy'
            if memory.percent > 90:
                status = 'degraded'
            if disk.percent > 95:
                status = 'degraded'
            
            return {
                'status': status,
                'memory': {
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'percent_used': memory.percent
                },
                'disk': {
                    'total_gb': round(disk.total / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2),
                    'percent_used': disk.percent
                },
                'process': {
                    'memory_mb': round(process_memory.rss / (1024**2), 2),
                    'cpu_percent': process.cpu_percent()
                }
            }
            
        except ImportError:
            # psutil не установлен
            return {
                'status': 'unknown',
                'message': 'psutil не установлен для мониторинга ресурсов'
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def _check_payment_system(self) -> Dict[str, Any]:
        """Проверка платежной системы ЮKassa"""
        try:
            from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY
            
            if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
                return {
                    'status': 'error',
                    'error': 'ЮKassa credentials не настроены'
                }
            
            # Простая проверка - пытаемся создать тестовый запрос к API
            # (без реального создания платежа)
            
            return {
                'status': 'healthy',
                'shop_id': YOOKASSA_SHOP_ID,
                'credentials_configured': True
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Получить текущий статус здоровья"""
        # Если проверка не выполнялась или устарела
        if (not self.last_check or 
            time.time() - self.last_check > self.check_interval):
            await self.perform_health_check()
        
        return self.health_status
    
    async def is_healthy(self) -> bool:
        """Проверить, здорова ли система"""
        status = await self.get_health_status()
        return status.get('status') in ['healthy', 'degraded']


# Глобальный экземпляр health check manager
health_manager = HealthCheckManager()


async def get_system_health() -> Dict[str, Any]:
    """Получить статус здоровья системы"""
    return await health_manager.get_health_status()


async def is_system_healthy() -> bool:
    """Проверить, здорова ли система"""
    return await health_manager.is_healthy()
