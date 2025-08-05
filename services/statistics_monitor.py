"""
Production-ready мониторинг и валидация статистики
Проверки целостности данных и автоматическое восстановление
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Результат валидации данных"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]
    checked_at: datetime


@dataclass
class HealthCheckResult:
    """Результат проверки здоровья системы"""
    status: str  # healthy, warning, critical
    database_status: str
    cache_status: str
    data_integrity: str
    performance_score: float
    issues: List[str]
    recommendations: List[str]
    checked_at: datetime


class StatisticsMonitor:
    """
    Production-ready мониторинг системы статистики
    """
    
    def __init__(self, statistics_service):
        self.stats_service = statistics_service
        self.validation_history = []
        self.health_history = []
        self.alert_thresholds = {
            'max_response_time': 5.0,  # секунд
            'min_cache_hit_rate': 0.7,  # 70%
            'max_error_rate': 0.05,  # 5%
            'data_freshness_hours': 1,  # час
        }
    
    async def validate_data_integrity(self) -> ValidationResult:
        """
        Проверить целостность данных статистики
        """
        errors = []
        warnings = []
        suggestions = []
        
        try:
            # Получаем базовую статистику
            basic_stats = await self.stats_service.get_basic_statistics()
            detailed_stats = await self.stats_service.get_detailed_statistics()
            
            # Проверка 1: Базовые числа не должны быть отрицательными
            if basic_stats.total_users < 0:
                errors.append("Отрицательное количество пользователей")
            
            if basic_stats.active_subscribers < 0:
                errors.append("Отрицательное количество подписчиков")
            
            if basic_stats.requests_today < 0:
                errors.append("Отрицательное количество запросов за сегодня")
            
            # Проверка 2: Логические ограничения
            if basic_stats.active_subscribers > basic_stats.total_users:
                errors.append("Подписчиков больше чем пользователей")
            
            # Проверка 3: Конверсия в разумных пределах
            if basic_stats.conversion_rate > 100:
                errors.append(f"Конверсия больше 100%: {basic_stats.conversion_rate}")
            elif basic_stats.conversion_rate < 0:
                errors.append(f"Отрицательная конверсия: {basic_stats.conversion_rate}")
            
            # Проверка 4: Свежесть данных
            data_age = datetime.now() - basic_stats.generated_at
            if data_age > timedelta(hours=self.alert_thresholds['data_freshness_hours']):
                warnings.append(f"Данные устарели на {data_age.total_seconds() / 3600:.1f} часов")
            
            # Проверка 5: Сравнение с детальной статистикой
            if detailed_stats:
                if abs(detailed_stats.get('total_users', 0) - basic_stats.total_users) > 0:
                    warnings.append("Расхождение в количестве пользователей между базовой и детальной статистикой")
                
                if abs(detailed_stats.get('active_subscribers', 0) - basic_stats.active_subscribers) > 0:
                    warnings.append("Расхождение в количестве подписчиков")
            
            # Проверка 6: Аномалии в данных
            await self._check_data_anomalies(basic_stats, detailed_stats, warnings, suggestions)
            
            # Проверка 7: Производительность
            await self._check_performance_metrics(warnings, suggestions)
            
            result = ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions,
                checked_at=datetime.now()
            )
            
            # Сохраняем результат в историю
            self.validation_history.append(result)
            
            # Ограничиваем историю последними 100 проверками
            if len(self.validation_history) > 100:
                self.validation_history = self.validation_history[-100:]
            
            logger.info(f"Валидация данных: {'✅ УСПЕШНО' if result.is_valid else '❌ ОШИБКИ'}")
            if errors:
                logger.error(f"Ошибки валидации: {errors}")
            if warnings:
                logger.warning(f"Предупреждения валидации: {warnings}")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка валидации данных: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"Критическая ошибка валидации: {e}"],
                warnings=[],
                suggestions=["Проверьте подключение к базе данных", "Перезапустите сервис статистики"],
                checked_at=datetime.now()
            )
    
    async def _check_data_anomalies(self, basic_stats, detailed_stats, warnings: List[str], suggestions: List[str]):
        """Проверить аномалии в данных"""
        try:
            # Проверяем резкие изменения
            if len(self.validation_history) > 0:
                last_check = self.validation_history[-1]
                
                # Если есть предыдущие данные, сравниваем
                # (здесь можно добавить более сложную логику)
                pass
            
            # Проверяем соотношения
            if basic_stats.total_users > 0:
                avg_requests = basic_stats.avg_requests_per_user
                if avg_requests > 100:
                    warnings.append(f"Очень высокое среднее количество запросов на пользователя: {avg_requests:.1f}")
                    suggestions.append("Проверьте на наличие ботов или злоупотреблений")
                elif avg_requests < 0.1 and basic_stats.total_users > 10:
                    warnings.append(f"Очень низкая активность пользователей: {avg_requests:.1f}")
                    suggestions.append("Рассмотрите улучшение пользовательского опыта")
            
            # Проверяем доходы
            if detailed_stats:
                revenue_today = detailed_stats.get('revenue_today', 0)
                payments_today = detailed_stats.get('successful_payments_today', 0)
                
                if revenue_today > 0 and payments_today == 0:
                    warnings.append("Есть доходы, но нет успешных платежей")
                elif revenue_today == 0 and payments_today > 0:
                    warnings.append("Есть успешные платежи, но нет доходов")
                
                # Проверяем среднюю стоимость подписки
                if payments_today > 0 and revenue_today > 0:
                    avg_payment = revenue_today / payments_today
                    if avg_payment < 100:  # Меньше 100 рублей
                        warnings.append(f"Низкая средняя стоимость платежа: {avg_payment:.2f} ₽")
                    elif avg_payment > 2000:  # Больше 2000 рублей
                        warnings.append(f"Высокая средняя стоимость платежа: {avg_payment:.2f} ₽")
        
        except Exception as e:
            logger.error(f"Ошибка проверки аномалий: {e}")
    
    async def _check_performance_metrics(self, warnings: List[str], suggestions: List[str]):
        """Проверить метрики производительности"""
        try:
            # Проверяем здоровье сервиса статистики
            health = await self.stats_service.get_health_status()
            
            if health['status'] != 'healthy':
                warnings.append(f"Сервис статистики не здоров: {health['status']}")
                if 'error' in health:
                    suggestions.append(f"Ошибка: {health['error']}")
            
            if not health.get('database_connected', False):
                warnings.append("Нет подключения к базе данных")
                suggestions.append("Проверьте настройки подключения к PostgreSQL")
            
            # Проверяем размер кеша
            cache_size = health.get('cache_size', 0)
            if cache_size > 1000:
                warnings.append(f"Большой размер кеша: {cache_size} элементов")
                suggestions.append("Рассмотрите уменьшение TTL кеша")
            elif cache_size == 0:
                suggestions.append("Кеш пуст - возможно, низкая эффективность")
        
        except Exception as e:
            logger.error(f"Ошибка проверки производительности: {e}")
    
    async def perform_health_check(self) -> HealthCheckResult:
        """
        Выполнить полную проверку здоровья системы
        """
        try:
            issues = []
            recommendations = []
            
            # Проверяем базу данных
            db_status = "healthy"
            if not await self.stats_service._validate_database_connection():
                db_status = "critical"
                issues.append("Нет подключения к базе данных")
                recommendations.append("Проверьте настройки PostgreSQL")
            
            # Проверяем кеш
            cache_status = "healthy"
            try:
                health = await self.stats_service.get_health_status()
                if health['status'] != 'healthy':
                    cache_status = "warning"
                    issues.append("Проблемы с кешем статистики")
            except:
                cache_status = "critical"
                issues.append("Критическая ошибка кеша")
            
            # Проверяем целостность данных
            validation = await self.validate_data_integrity()
            data_integrity = "healthy"
            if validation.errors:
                data_integrity = "critical"
                issues.extend(validation.errors)
            elif validation.warnings:
                data_integrity = "warning"
                issues.extend(validation.warnings)
            
            recommendations.extend(validation.suggestions)
            
            # Вычисляем общий статус
            if db_status == "critical" or data_integrity == "critical":
                overall_status = "critical"
            elif db_status == "warning" or cache_status == "warning" or data_integrity == "warning":
                overall_status = "warning"
            else:
                overall_status = "healthy"
            
            # Вычисляем оценку производительности
            performance_score = await self._calculate_performance_score(db_status, cache_status, data_integrity)
            
            result = HealthCheckResult(
                status=overall_status,
                database_status=db_status,
                cache_status=cache_status,
                data_integrity=data_integrity,
                performance_score=performance_score,
                issues=issues,
                recommendations=recommendations,
                checked_at=datetime.now()
            )
            
            # Сохраняем в историю
            self.health_history.append(result)
            if len(self.health_history) > 50:
                self.health_history = self.health_history[-50:]
            
            logger.info(f"Health check: {overall_status.upper()} (score: {performance_score:.1f})")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка health check: {e}")
            return HealthCheckResult(
                status="critical",
                database_status="unknown",
                cache_status="unknown",
                data_integrity="unknown",
                performance_score=0.0,
                issues=[f"Критическая ошибка мониторинга: {e}"],
                recommendations=["Перезапустите систему мониторинга"],
                checked_at=datetime.now()
            )
    
    async def _calculate_performance_score(self, db_status: str, cache_status: str, data_integrity: str) -> float:
        """Вычислить оценку производительности (0-100)"""
        score = 100.0
        
        # Штрафы за проблемы
        if db_status == "critical":
            score -= 50
        elif db_status == "warning":
            score -= 20
        
        if cache_status == "critical":
            score -= 30
        elif cache_status == "warning":
            score -= 10
        
        if data_integrity == "critical":
            score -= 40
        elif data_integrity == "warning":
            score -= 15
        
        return max(0.0, score)
    
    async def auto_fix_issues(self) -> Dict[str, Any]:
        """
        Автоматическое исправление обнаруженных проблем
        """
        fixed_issues = []
        failed_fixes = []
        
        try:
            # Проверяем текущее состояние
            health = await self.perform_health_check()
            
            # Исправляем проблемы с кешем
            if health.cache_status != "healthy":
                try:
                    await self.stats_service.invalidate_cache()
                    fixed_issues.append("Кеш статистики очищен")
                except Exception as e:
                    failed_fixes.append(f"Не удалось очистить кеш: {e}")
            
            # Можно добавить другие автоматические исправления
            
            logger.info(f"Автоисправление: {len(fixed_issues)} исправлено, {len(failed_fixes)} неудач")
            
            return {
                'fixed_issues': fixed_issues,
                'failed_fixes': failed_fixes,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка автоисправления: {e}")
            return {
                'fixed_issues': [],
                'failed_fixes': [f"Критическая ошибка: {e}"],
                'timestamp': datetime.now().isoformat()
            }
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Получить сводку мониторинга"""
        return {
            'validation_history_count': len(self.validation_history),
            'health_history_count': len(self.health_history),
            'last_validation': self.validation_history[-1].__dict__ if self.validation_history else None,
            'last_health_check': self.health_history[-1].__dict__ if self.health_history else None,
            'alert_thresholds': self.alert_thresholds
        }
