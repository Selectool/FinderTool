"""
Production-ready сервис статистики с кешированием и валидацией
Централизованное управление всей статистикой системы
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import json
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class StatisticsData:
    """Структура данных статистики"""
    total_users: int = 0
    active_subscribers: int = 0
    requests_today: int = 0
    requests_week: int = 0
    requests_month: int = 0
    new_users_today: int = 0
    new_users_week: int = 0
    new_users_month: int = 0
    revenue_today: int = 0
    revenue_week: int = 0
    revenue_month: int = 0
    payments_today: int = 0
    payments_week: int = 0
    payments_month: int = 0
    successful_payments_today: int = 0
    successful_payments_week: int = 0
    successful_payments_month: int = 0
    broadcasts_total: int = 0
    broadcasts_completed: int = 0
    conversion_rate: float = 0.0
    avg_requests_per_user: float = 0.0
    generated_at: datetime = None

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now()


class StatisticsCache:
    """Кеш для статистики с TTL"""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 минут по умолчанию
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кеша"""
        async with self._lock:
            if key in self._cache:
                data = self._cache[key]
                if datetime.now() - data['timestamp'] < timedelta(seconds=self.ttl_seconds):
                    logger.debug(f"Cache HIT для ключа: {key}")
                    return data['value']
                else:
                    # Удаляем устаревшие данные
                    del self._cache[key]
                    logger.debug(f"Cache EXPIRED для ключа: {key}")
            
            logger.debug(f"Cache MISS для ключа: {key}")
            return None
    
    async def set(self, key: str, value: Any):
        """Установить значение в кеш"""
        async with self._lock:
            self._cache[key] = {
                'value': value,
                'timestamp': datetime.now()
            }
            logger.debug(f"Cache SET для ключа: {key}")
    
    async def invalidate(self, pattern: str = None):
        """Инвалидировать кеш"""
        async with self._lock:
            if pattern:
                keys_to_remove = [k for k in self._cache.keys() if pattern in k]
                for key in keys_to_remove:
                    del self._cache[key]
                logger.info(f"Инвалидирован кеш по паттерну: {pattern}")
            else:
                self._cache.clear()
                logger.info("Весь кеш инвалидирован")


def cache_result(cache_key: str, ttl: int = 300):
    """Декоратор для кеширования результатов методов"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Формируем ключ кеша с учетом аргументов
            key = f"{cache_key}:{hash(str(args) + str(kwargs))}"
            
            # Пытаемся получить из кеша
            cached_result = await self.cache.get(key)
            if cached_result is not None:
                return cached_result
            
            # Выполняем функцию и кешируем результат
            result = await func(self, *args, **kwargs)
            await self.cache.set(key, result)
            return result
        return wrapper
    return decorator


class StatisticsService:
    """
    Production-ready сервис статистики с кешированием и валидацией
    """
    
    def __init__(self, db, cache_ttl: int = 300):
        """
        Инициализация сервиса статистики
        
        Args:
            db: Экземпляр UniversalDatabase
            cache_ttl: Время жизни кеша в секундах
        """
        self.db = db
        self.cache = StatisticsCache(cache_ttl)
        self._validation_enabled = True
    
    async def _validate_database_connection(self) -> bool:
        """Проверка подключения к базе данных"""
        try:
            await self.db.adapter.connect()
            # Простой тест запрос
            await self.db.adapter.fetch_one("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            return False
        finally:
            try:
                await self.db.adapter.disconnect()
            except:
                pass
    
    @cache_result("basic_stats", ttl=180)  # 3 минуты
    async def get_basic_statistics(self) -> StatisticsData:
        """
        Получить базовую статистику (для бота)
        """
        try:
            if not await self._validate_database_connection():
                logger.error("Нет подключения к БД для получения базовой статистики")
                return StatisticsData()
            
            await self.db.adapter.connect()
            stats = StatisticsData()
            
            # Общее количество пользователей
            result = await self.db.adapter.fetch_one("SELECT COUNT(*) FROM users")
            stats.total_users = self._extract_count(result)
            
            # Активные подписчики
            if self.db.adapter.db_type == 'sqlite':
                query = """
                    SELECT COUNT(*) FROM users
                    WHERE is_subscribed = 1
                    AND (subscription_end IS NULL OR subscription_end > datetime('now'))
                """
            else:  # PostgreSQL
                query = """
                    SELECT COUNT(*) FROM users
                    WHERE is_subscribed = TRUE
                    AND (subscription_end IS NULL OR subscription_end > NOW())
                """
            
            result = await self.db.adapter.fetch_one(query)
            stats.active_subscribers = self._extract_count(result)
            
            # Запросы за сегодня
            today = datetime.now().date()
            if self.db.adapter.db_type == 'sqlite':
                query = "SELECT COUNT(*) FROM requests WHERE DATE(created_at) = ?"
                params = (today,)
            else:  # PostgreSQL
                query = "SELECT COUNT(*) FROM requests WHERE DATE(created_at) = $1"
                params = (today,)
            
            result = await self.db.adapter.fetch_one(query, params)
            stats.requests_today = self._extract_count(result)
            
            # Вычисляем конверсию
            if stats.total_users > 0:
                stats.conversion_rate = (stats.active_subscribers / stats.total_users) * 100
            
            # Средние запросы на пользователя
            if stats.total_users > 0:
                total_requests_result = await self.db.adapter.fetch_one("SELECT COUNT(*) FROM requests")
                total_requests = self._extract_count(total_requests_result)
                stats.avg_requests_per_user = total_requests / stats.total_users
            
            logger.info(f"Базовая статистика получена: {stats.total_users} пользователей, {stats.active_subscribers} подписчиков")
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка получения базовой статистики: {e}")
            return StatisticsData()
        finally:
            try:
                await self.db.adapter.disconnect()
            except:
                pass
    
    @cache_result("detailed_stats", ttl=300)  # 5 минут
    async def get_detailed_statistics(self) -> Dict[str, Any]:
        """
        Получить детальную статистику (для админ-панели)
        """
        try:
            if not await self._validate_database_connection():
                logger.error("Нет подключения к БД для получения детальной статистики")
                return {}
            
            await self.db.adapter.connect()
            stats = {}
            
            # Базовая статистика
            basic_stats = await self.get_basic_statistics()
            stats.update(asdict(basic_stats))
            
            # Дополнительная статистика пользователей
            await self._add_user_statistics(stats)
            
            # Статистика запросов
            await self._add_request_statistics(stats)
            
            # Статистика платежей
            await self._add_payment_statistics(stats)
            
            # Статистика рассылок
            await self._add_broadcast_statistics(stats)
            
            # Топ пользователей
            await self._add_top_users(stats)
            
            stats['generated_at'] = datetime.now().isoformat()
            logger.info("Детальная статистика успешно сформирована")
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка получения детальной статистики: {e}")
            return {}
        finally:
            try:
                await self.db.adapter.disconnect()
            except:
                pass
    
    def _extract_count(self, result) -> int:
        """Извлечь число из результата запроса"""
        if result is None:
            return 0
        if isinstance(result, (list, tuple)):
            return result[0] if result else 0
        if isinstance(result, dict):
            # Ищем первое числовое значение
            for value in result.values():
                if isinstance(value, int):
                    return value
        if isinstance(result, int):
            return result
        return 0

    async def _add_user_statistics(self, stats: Dict[str, Any]):
        """Добавить статистику пользователей"""
        try:
            # Новые пользователи за периоды
            today = datetime.now().date()
            week_ago = datetime.now() - timedelta(days=7)
            month_ago = datetime.now() - timedelta(days=30)

            if self.db.adapter.db_type == 'sqlite':
                # Новые пользователи сегодня
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM users WHERE DATE(created_at) = ?", (today,)
                )
                stats['new_users_today'] = self._extract_count(result)

                # Новые пользователи за неделю
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM users WHERE created_at >= ?", (week_ago,)
                )
                stats['new_users_week'] = self._extract_count(result)

                # Новые пользователи за месяц
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM users WHERE created_at >= ?", (month_ago,)
                )
                stats['new_users_month'] = self._extract_count(result)

            else:  # PostgreSQL
                # Новые пользователи сегодня
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM users WHERE DATE(created_at) = $1", (today,)
                )
                stats['new_users_today'] = self._extract_count(result)

                # Новые пользователи за неделю
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM users WHERE created_at >= $1", (week_ago,)
                )
                stats['new_users_week'] = self._extract_count(result)

                # Новые пользователи за месяц
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM users WHERE created_at >= $1", (month_ago,)
                )
                stats['new_users_month'] = self._extract_count(result)

            # Заблокированные пользователи
            result = await self.db.adapter.fetch_one("SELECT COUNT(*) FROM users WHERE blocked = TRUE")
            stats['blocked_users'] = self._extract_count(result)

            # Пользователи с безлимитным доступом
            result = await self.db.adapter.fetch_one("SELECT COUNT(*) FROM users WHERE unlimited_access = TRUE")
            stats['unlimited_users'] = self._extract_count(result)

        except Exception as e:
            logger.error(f"Ошибка получения статистики пользователей: {e}")

    async def _add_request_statistics(self, stats: Dict[str, Any]):
        """
        Добавить статистику запросов (ИСПРАВЛЕНО)
        Production-ready подсчет с правильными временными интервалами
        """
        try:
            # Точные временные границы
            now = datetime.now()
            today_start = datetime.combine(now.date(), datetime.min.time())
            week_start = now - timedelta(days=7)

            # Начало текущего месяца (правильный подсчет)
            month_start = datetime(now.year, now.month, 1)

            if self.db.adapter.db_type == 'sqlite':
                # Запросы сегодня
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM requests WHERE created_at >= ?", (today_start,)
                )
                stats['requests_today'] = self._extract_count(result)

                # Запросы за неделю
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM requests WHERE created_at >= ?", (week_start,)
                )
                stats['requests_week'] = self._extract_count(result)

                # Запросы за текущий месяц (с начала месяца)
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM requests WHERE created_at >= ?", (month_start,)
                )
                stats['requests_month'] = self._extract_count(result)

            else:  # PostgreSQL
                # Запросы сегодня
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM requests WHERE created_at >= $1", (today_start,)
                )
                stats['requests_today'] = self._extract_count(result)

                # Запросы за неделю
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM requests WHERE created_at >= $1", (week_start,)
                )
                stats['requests_week'] = self._extract_count(result)

                # Запросы за текущий месяц (с начала месяца)
                result = await self.db.adapter.fetch_one(
                    "SELECT COUNT(*) FROM requests WHERE created_at >= $1", (month_start,)
                )
                stats['requests_month'] = self._extract_count(result)

            # Общее количество запросов за все время
            result = await self.db.adapter.fetch_one("SELECT COUNT(*) FROM requests")
            stats['total_requests'] = self._extract_count(result)

            logger.debug(f"Статистика запросов: сегодня={stats.get('requests_today', 0)}, "
                        f"неделя={stats.get('requests_week', 0)}, "
                        f"месяц={stats.get('requests_month', 0)}, "
                        f"всего={stats.get('total_requests', 0)}")

        except Exception as e:
            logger.error(f"Ошибка получения статистики запросов: {e}")
            # Устанавливаем значения по умолчанию при ошибке
            stats.update({
                'requests_today': 0,
                'requests_week': 0,
                'requests_month': 0,
                'total_requests': 0
            })

    async def _add_payment_statistics(self, stats: Dict[str, Any]):
        """
        Добавить статистику платежей (ИСПРАВЛЕНО)
        Production-ready подсчет доходов с правильными временными интервалами
        """
        try:
            # Точные временные границы
            now = datetime.now()
            today_start = datetime.combine(now.date(), datetime.min.time())
            week_start = now - timedelta(days=7)

            # Начало текущего месяца (правильный подсчет)
            month_start = datetime(now.year, now.month, 1)

            if self.db.adapter.db_type == 'sqlite':
                # Платежи сегодня
                result = await self.db.adapter.fetch_one("""
                    SELECT
                        COUNT(*) as count,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as revenue,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful
                    FROM payments
                    WHERE created_at >= ?
                """, (today_start,))

                if result:
                    stats['payments_today'] = result[0] if result[0] else 0
                    stats['revenue_today'] = (result[1] if result[1] else 0) // 100  # Конвертируем копейки в рубли
                    stats['successful_payments_today'] = result[2] if result[2] else 0

                # Платежи за неделю
                result = await self.db.adapter.fetch_one("""
                    SELECT
                        COUNT(*) as count,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as revenue,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful
                    FROM payments
                    WHERE created_at >= ?
                """, (week_start,))

                if result:
                    stats['payments_week'] = result[0] if result[0] else 0
                    stats['revenue_week'] = (result[1] if result[1] else 0) // 100
                    stats['successful_payments_week'] = result[2] if result[2] else 0

                # Платежи за текущий месяц (с начала месяца)
                result = await self.db.adapter.fetch_one("""
                    SELECT
                        COUNT(*) as count,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as revenue,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful
                    FROM payments
                    WHERE created_at >= ?
                """, (month_start,))

                if result:
                    stats['payments_month'] = result[0] if result[0] else 0
                    stats['revenue_month'] = (result[1] if result[1] else 0) // 100
                    stats['successful_payments_month'] = result[2] if result[2] else 0

            else:  # PostgreSQL
                # Платежи сегодня
                result = await self.db.adapter.fetch_one("""
                    SELECT
                        COUNT(*) as count,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as revenue,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful
                    FROM payments
                    WHERE created_at >= $1
                """, (today_start,))

                if result:
                    if isinstance(result, dict):
                        stats['payments_today'] = result.get('count', 0)
                        stats['revenue_today'] = (result.get('revenue', 0)) // 100
                        stats['successful_payments_today'] = result.get('successful', 0)
                    else:
                        stats['payments_today'] = result[0] if result[0] else 0
                        stats['revenue_today'] = (result[1] if result[1] else 0) // 100
                        stats['successful_payments_today'] = result[2] if result[2] else 0

                # Платежи за неделю
                result = await self.db.adapter.fetch_one("""
                    SELECT
                        COUNT(*) as count,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as revenue,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful
                    FROM payments
                    WHERE created_at >= $1
                """, (week_start,))

                if result:
                    if isinstance(result, dict):
                        stats['payments_week'] = result.get('count', 0)
                        stats['revenue_week'] = (result.get('revenue', 0)) // 100
                        stats['successful_payments_week'] = result.get('successful', 0)
                    else:
                        stats['payments_week'] = result[0] if result[0] else 0
                        stats['revenue_week'] = (result[1] if result[1] else 0) // 100
                        stats['successful_payments_week'] = result[2] if result[2] else 0

                # Платежи за текущий месяц (с начала месяца)
                result = await self.db.adapter.fetch_one("""
                    SELECT
                        COUNT(*) as count,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as revenue,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful
                    FROM payments
                    WHERE created_at >= $1
                """, (month_start,))

                if result:
                    if isinstance(result, dict):
                        stats['payments_month'] = result.get('count', 0)
                        stats['revenue_month'] = (result.get('revenue', 0)) // 100
                        stats['successful_payments_month'] = result.get('successful', 0)
                    else:
                        stats['payments_month'] = result[0] if result[0] else 0
                        stats['revenue_month'] = (result[1] if result[1] else 0) // 100
                        stats['successful_payments_month'] = result[2] if result[2] else 0

            # Общая статистика платежей за все время
            result = await self.db.adapter.fetch_one("""
                SELECT
                    COUNT(*) as count,
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as revenue,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful
                FROM payments
            """)

            if result:
                if isinstance(result, dict):
                    stats['payments_total'] = result.get('count', 0)
                    stats['revenue_total'] = (result.get('revenue', 0)) // 100
                    stats['successful_payments_total'] = result.get('successful', 0)
                else:
                    stats['payments_total'] = result[0] if result[0] else 0
                    stats['revenue_total'] = (result[1] if result[1] else 0) // 100
                    stats['successful_payments_total'] = result[2] if result[2] else 0

            logger.debug(f"Статистика платежей: сегодня={stats.get('revenue_today', 0)}₽, "
                        f"неделя={stats.get('revenue_week', 0)}₽, "
                        f"месяц={stats.get('revenue_month', 0)}₽, "
                        f"всего={stats.get('revenue_total', 0)}₽")

        except Exception as e:
            logger.error(f"Ошибка получения статистики платежей: {e}")
            # Устанавливаем значения по умолчанию при ошибке
            stats.update({
                'payments_today': 0,
                'revenue_today': 0,
                'successful_payments_today': 0,
                'payments_week': 0,
                'revenue_week': 0,
                'successful_payments_week': 0,
                'payments_month': 0,
                'revenue_month': 0,
                'successful_payments_month': 0,
                'payments_total': 0,
                'revenue_total': 0,
                'successful_payments_total': 0
            })

    async def _add_broadcast_statistics(self, stats: Dict[str, Any]):
        """Добавить статистику рассылок"""
        try:
            # Общая статистика рассылок
            result = await self.db.adapter.fetch_one("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN completed = TRUE THEN 1 END) as completed,
                    COALESCE(SUM(sent_count), 0) as total_sent,
                    COALESCE(SUM(failed_count), 0) as total_failed
                FROM broadcasts
            """)

            if result:
                if isinstance(result, dict):
                    stats['broadcasts_total'] = result.get('total', 0)
                    stats['broadcasts_completed'] = result.get('completed', 0)
                    stats['broadcasts_sent'] = result.get('total_sent', 0)
                    stats['broadcasts_failed'] = result.get('total_failed', 0)
                else:
                    stats['broadcasts_total'] = result[0] if result[0] else 0
                    stats['broadcasts_completed'] = result[1] if result[1] else 0
                    stats['broadcasts_sent'] = result[2] if result[2] else 0
                    stats['broadcasts_failed'] = result[3] if result[3] else 0

        except Exception as e:
            logger.error(f"Ошибка получения статистики рассылок: {e}")
            stats.update({
                'broadcasts_total': 0,
                'broadcasts_completed': 0,
                'broadcasts_sent': 0,
                'broadcasts_failed': 0
            })

    async def _add_top_users(self, stats: Dict[str, Any]):
        """
        Добавить топ пользователей с информацией о последней активности
        ИСПРАВЛЕНО: Добавлена последняя активность пользователей
        """
        try:
            # Получаем топ пользователей с последней активностью из запросов
            result = await self.db.adapter.fetch_all("""
                SELECT
                    u.user_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    u.requests_used,
                    u.is_subscribed,
                    u.subscription_end,
                    COALESCE(MAX(r.created_at), u.created_at) as last_activity
                FROM users u
                LEFT JOIN requests r ON u.user_id = r.user_id
                WHERE u.requests_used > 0
                GROUP BY u.user_id, u.username, u.first_name, u.last_name, u.requests_used, u.is_subscribed, u.subscription_end, u.created_at
                ORDER BY u.requests_used DESC, last_activity DESC
                LIMIT 10
            """)

            top_users = []
            for row in result:
                if isinstance(row, dict):
                    user_data = row.copy()
                    # Форматируем дату последней активности
                    if user_data.get('last_activity'):
                        if isinstance(user_data['last_activity'], str):
                            try:
                                from datetime import datetime
                                last_activity = datetime.fromisoformat(user_data['last_activity'].replace('Z', '+00:00'))
                                user_data['last_activity_formatted'] = last_activity.strftime('%d.%m.%Y %H:%M')
                            except:
                                user_data['last_activity_formatted'] = 'Неизвестно'
                        else:
                            user_data['last_activity_formatted'] = user_data['last_activity'].strftime('%d.%m.%Y %H:%M')
                    else:
                        user_data['last_activity_formatted'] = 'Неизвестно'

                    # Определяем статус пользователя
                    if user_data.get('is_subscribed'):
                        user_data['status'] = 'Подписчик'
                        user_data['status_class'] = 'success'
                    else:
                        user_data['status'] = 'Обычный'
                        user_data['status_class'] = 'secondary'

                    top_users.append(user_data)
                else:
                    # Обработка tuple результата
                    user_data = {
                        'user_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'requests_used': row[4],
                        'is_subscribed': row[5] if len(row) > 5 else False,
                        'subscription_end': row[6] if len(row) > 6 else None,
                        'last_activity': row[7] if len(row) > 7 else None
                    }

                    # Форматируем дату
                    if user_data['last_activity']:
                        try:
                            if isinstance(user_data['last_activity'], str):
                                from datetime import datetime
                                last_activity = datetime.fromisoformat(user_data['last_activity'].replace('Z', '+00:00'))
                            else:
                                last_activity = user_data['last_activity']
                            user_data['last_activity_formatted'] = last_activity.strftime('%d.%m.%Y %H:%M')
                        except:
                            user_data['last_activity_formatted'] = 'Неизвестно'
                    else:
                        user_data['last_activity_formatted'] = 'Неизвестно'

                    # Статус
                    if user_data['is_subscribed']:
                        user_data['status'] = 'Подписчик'
                        user_data['status_class'] = 'success'
                    else:
                        user_data['status'] = 'Обычный'
                        user_data['status_class'] = 'secondary'

                    top_users.append(user_data)

            stats['top_users'] = top_users
            logger.info(f"Получено {len(top_users)} топ пользователей с активностью")

        except Exception as e:
            logger.error(f"Ошибка получения топ пользователей: {e}")
            stats['top_users'] = []

    @cache_result("payment_stats", ttl=120)  # 2 минуты
    async def get_payment_statistics(self) -> Dict[str, Any]:
        """
        Получить статистику платежей (для команды /payment_stats)
        """
        try:
            if not await self._validate_database_connection():
                logger.error("Нет подключения к БД для получения статистики платежей")
                return self._get_empty_payment_stats()

            await self.db.adapter.connect()
            stats = {
                'today': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
                'week': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
                'month': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
                'total': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0}
            }

            today = datetime.now().date()
            week_ago = datetime.now() - timedelta(days=7)
            month_ago = datetime.now() - timedelta(days=30)

            # Статистика за сегодня
            await self._get_payment_stats_for_period(stats, 'today', today, is_date=True)

            # Статистика за неделю
            await self._get_payment_stats_for_period(stats, 'week', week_ago, is_date=False)

            # Статистика за месяц
            await self._get_payment_stats_for_period(stats, 'month', month_ago, is_date=False)

            # Общая статистика
            await self._get_payment_stats_for_period(stats, 'total', None, is_date=False)

            logger.info("Статистика платежей успешно получена")
            return stats

        except Exception as e:
            logger.error(f"Ошибка получения статистики платежей: {e}")
            return self._get_empty_payment_stats()
        finally:
            try:
                await self.db.adapter.disconnect()
            except:
                pass

    def _get_empty_payment_stats(self) -> Dict[str, Any]:
        """Получить пустую статистику платежей"""
        return {
            'today': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
            'week': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
            'month': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0},
            'total': {'count': 0, 'amount': 0, 'successful': 0, 'pending': 0, 'failed': 0}
        }

    async def _get_payment_stats_for_period(self, stats: Dict, period: str, date_filter, is_date: bool):
        """Получить статистику платежей за период"""
        try:
            if date_filter is None:
                # Общая статистика
                query = """
                    SELECT
                        COUNT(*) as total_count,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as successful_amount,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_count,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                        COUNT(CASE WHEN status IN ('cancelled', 'failed') THEN 1 END) as failed_count
                    FROM payments
                """
                params = ()
            elif is_date:
                # За конкретную дату
                if self.db.adapter.db_type == 'sqlite':
                    query = """
                        SELECT
                            COUNT(*) as total_count,
                            COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as successful_amount,
                            COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_count,
                            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                            COUNT(CASE WHEN status IN ('cancelled', 'failed') THEN 1 END) as failed_count
                        FROM payments
                        WHERE DATE(created_at) = ?
                    """
                    params = (date_filter,)
                else:  # PostgreSQL
                    query = """
                        SELECT
                            COUNT(*) as total_count,
                            COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as successful_amount,
                            COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_count,
                            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                            COUNT(CASE WHEN status IN ('cancelled', 'failed') THEN 1 END) as failed_count
                        FROM payments
                        WHERE DATE(created_at) = $1
                    """
                    params = (date_filter,)
            else:
                # За период от даты
                if self.db.adapter.db_type == 'sqlite':
                    query = """
                        SELECT
                            COUNT(*) as total_count,
                            COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as successful_amount,
                            COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_count,
                            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                            COUNT(CASE WHEN status IN ('cancelled', 'failed') THEN 1 END) as failed_count
                        FROM payments
                        WHERE created_at >= ?
                    """
                    params = (date_filter,)
                else:  # PostgreSQL
                    query = """
                        SELECT
                            COUNT(*) as total_count,
                            COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as successful_amount,
                            COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_count,
                            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                            COUNT(CASE WHEN status IN ('cancelled', 'failed') THEN 1 END) as failed_count
                        FROM payments
                        WHERE created_at >= $1
                    """
                    params = (date_filter,)

            result = await self.db.adapter.fetch_one(query, params)

            if result:
                if isinstance(result, dict):
                    stats[period] = {
                        'count': result.get('successful_count', 0),  # Только успешные платежи
                        'amount': result.get('successful_amount', 0),  # Только сумма успешных
                        'successful': result.get('successful_count', 0),
                        'pending': result.get('pending_count', 0),
                        'failed': result.get('failed_count', 0)
                    }
                else:
                    stats[period] = {
                        'count': result[2] if len(result) > 2 else 0,  # successful_count
                        'amount': result[1] if len(result) > 1 else 0,  # successful_amount
                        'successful': result[2] if len(result) > 2 else 0,
                        'pending': result[3] if len(result) > 3 else 0,
                        'failed': result[4] if len(result) > 4 else 0
                    }

        except Exception as e:
            logger.error(f"Ошибка получения статистики платежей за период {period}: {e}")

    async def invalidate_cache(self, pattern: str = None):
        """Инвалидировать кеш статистики"""
        await self.cache.invalidate(pattern)
        logger.info(f"Кеш статистики инвалидирован: {pattern or 'весь кеш'}")

    async def get_health_status(self) -> Dict[str, Any]:
        """Получить статус здоровья сервиса статистики"""
        try:
            db_connected = await self._validate_database_connection()
            cache_size = len(self.cache._cache)

            return {
                'status': 'healthy' if db_connected else 'unhealthy',
                'database_connected': db_connected,
                'cache_size': cache_size,
                'cache_ttl': self.cache.ttl_seconds,
                'validation_enabled': self._validation_enabled,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Ошибка проверки здоровья сервиса: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
