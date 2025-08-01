"""
Система мониторинга базы данных для production-ready уровня
"""
import asyncio
import logging
import time
import psutil
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DatabaseMetrics:
    """Метрики базы данных"""
    timestamp: datetime
    file_size: int
    connection_count: int
    query_time_avg: float
    query_time_max: float
    queries_per_second: float
    cache_hit_ratio: float
    disk_usage: float
    memory_usage: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'file_size': self.file_size,
            'connection_count': self.connection_count,
            'query_time_avg': self.query_time_avg,
            'query_time_max': self.query_time_max,
            'queries_per_second': self.queries_per_second,
            'cache_hit_ratio': self.cache_hit_ratio,
            'disk_usage': self.disk_usage,
            'memory_usage': self.memory_usage
        }


class DatabaseMonitor:
    """Монитор производительности базы данных"""
    
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.metrics_history: List[DatabaseMetrics] = []
        self.query_times: List[float] = []
        self.query_count = 0
        self.start_time = time.time()
        
        # Настройки мониторинга
        self.max_history_size = 1000
        self.alert_thresholds = {
            'query_time_max': 5.0,      # 5 секунд
            'queries_per_second': 100,   # 100 запросов в секунду
            'file_size_mb': 1000,       # 1GB
            'disk_usage_percent': 90,    # 90% диска
            'memory_usage_mb': 500      # 500MB памяти
        }
        
        # Логи метрик
        self.metrics_log_dir = Path("logs/metrics")
        self.metrics_log_dir.mkdir(parents=True, exist_ok=True)
    
    async def collect_metrics(self) -> DatabaseMetrics:
        """Собрать текущие метрики"""
        try:
            # Размер файла базы данных
            file_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            # Статистика запросов
            current_time = time.time()
            elapsed_time = current_time - self.start_time
            queries_per_second = self.query_count / elapsed_time if elapsed_time > 0 else 0
            
            query_time_avg = sum(self.query_times) / len(self.query_times) if self.query_times else 0
            query_time_max = max(self.query_times) if self.query_times else 0
            
            # Использование диска
            disk_usage = psutil.disk_usage(os.path.dirname(os.path.abspath(self.db_path)))
            disk_usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            # Использование памяти процессом
            process = psutil.Process()
            memory_usage = process.memory_info().rss / 1024 / 1024  # MB
            
            # Создаем метрики
            metrics = DatabaseMetrics(
                timestamp=datetime.now(),
                file_size=file_size,
                connection_count=0,  # TODO: Реализовать подсчет подключений
                query_time_avg=query_time_avg,
                query_time_max=query_time_max,
                queries_per_second=queries_per_second,
                cache_hit_ratio=0.0,  # TODO: Реализовать подсчет cache hit ratio
                disk_usage=disk_usage_percent,
                memory_usage=memory_usage
            )
            
            # Добавляем в историю
            self.metrics_history.append(metrics)
            
            # Ограничиваем размер истории
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history = self.metrics_history[-self.max_history_size:]
            
            # Очищаем старые времена запросов (оставляем последние 100)
            if len(self.query_times) > 100:
                self.query_times = self.query_times[-100:]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Ошибка сбора метрик: {e}")
            raise
    
    def record_query_time(self, query_time: float):
        """Записать время выполнения запроса"""
        self.query_times.append(query_time)
        self.query_count += 1
    
    async def check_alerts(self, metrics: DatabaseMetrics) -> List[Dict[str, Any]]:
        """Проверить пороги для алертов"""
        alerts = []
        
        # Проверка времени выполнения запросов
        if metrics.query_time_max > self.alert_thresholds['query_time_max']:
            alerts.append({
                'type': 'slow_query',
                'severity': 'warning',
                'message': f"Медленный запрос: {metrics.query_time_max:.2f}s",
                'value': metrics.query_time_max,
                'threshold': self.alert_thresholds['query_time_max']
            })
        
        # Проверка нагрузки
        if metrics.queries_per_second > self.alert_thresholds['queries_per_second']:
            alerts.append({
                'type': 'high_load',
                'severity': 'warning',
                'message': f"Высокая нагрузка: {metrics.queries_per_second:.1f} QPS",
                'value': metrics.queries_per_second,
                'threshold': self.alert_thresholds['queries_per_second']
            })
        
        # Проверка размера файла
        file_size_mb = metrics.file_size / 1024 / 1024
        if file_size_mb > self.alert_thresholds['file_size_mb']:
            alerts.append({
                'type': 'large_database',
                'severity': 'info',
                'message': f"Большой размер БД: {file_size_mb:.1f}MB",
                'value': file_size_mb,
                'threshold': self.alert_thresholds['file_size_mb']
            })
        
        # Проверка использования диска
        if metrics.disk_usage > self.alert_thresholds['disk_usage_percent']:
            alerts.append({
                'type': 'disk_space',
                'severity': 'critical',
                'message': f"Мало места на диске: {metrics.disk_usage:.1f}%",
                'value': metrics.disk_usage,
                'threshold': self.alert_thresholds['disk_usage_percent']
            })
        
        # Проверка использования памяти
        if metrics.memory_usage > self.alert_thresholds['memory_usage_mb']:
            alerts.append({
                'type': 'memory_usage',
                'severity': 'warning',
                'message': f"Высокое использование памяти: {metrics.memory_usage:.1f}MB",
                'value': metrics.memory_usage,
                'threshold': self.alert_thresholds['memory_usage_mb']
            })
        
        return alerts
    
    async def save_metrics_to_file(self, metrics: DatabaseMetrics):
        """Сохранить метрики в файл"""
        try:
            date_str = metrics.timestamp.strftime("%Y%m%d")
            metrics_file = self.metrics_log_dir / f"db_metrics_{date_str}.jsonl"
            
            with open(metrics_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(metrics.to_dict(), ensure_ascii=False) + '\n')
                
        except Exception as e:
            logger.error(f"Ошибка сохранения метрик: {e}")
    
    def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Получить сводку метрик за указанный период"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        
        if not recent_metrics:
            return {'error': 'Нет данных за указанный период'}
        
        # Вычисляем статистику
        query_times_avg = [m.query_time_avg for m in recent_metrics if m.query_time_avg > 0]
        query_times_max = [m.query_time_max for m in recent_metrics if m.query_time_max > 0]
        qps_values = [m.queries_per_second for m in recent_metrics]
        file_sizes = [m.file_size for m in recent_metrics]
        
        summary = {
            'period_hours': hours,
            'data_points': len(recent_metrics),
            'query_performance': {
                'avg_time_min': min(query_times_avg) if query_times_avg else 0,
                'avg_time_max': max(query_times_avg) if query_times_avg else 0,
                'avg_time_mean': sum(query_times_avg) / len(query_times_avg) if query_times_avg else 0,
                'max_time_peak': max(query_times_max) if query_times_max else 0
            },
            'load': {
                'qps_min': min(qps_values) if qps_values else 0,
                'qps_max': max(qps_values) if qps_values else 0,
                'qps_avg': sum(qps_values) / len(qps_values) if qps_values else 0
            },
            'storage': {
                'file_size_current': recent_metrics[-1].file_size,
                'file_size_min': min(file_sizes),
                'file_size_max': max(file_sizes),
                'growth_bytes': recent_metrics[-1].file_size - recent_metrics[0].file_size if len(recent_metrics) > 1 else 0
            },
            'system': {
                'disk_usage_current': recent_metrics[-1].disk_usage,
                'memory_usage_current': recent_metrics[-1].memory_usage
            }
        }
        
        return summary
    
    async def generate_report(self) -> Dict[str, Any]:
        """Сгенерировать отчет о состоянии базы данных"""
        try:
            # Собираем текущие метрики
            current_metrics = await self.collect_metrics()
            
            # Проверяем алерты
            alerts = await self.check_alerts(current_metrics)
            
            # Получаем сводку за 24 часа
            summary_24h = self.get_metrics_summary(24)
            
            # Получаем сводку за неделю
            summary_week = self.get_metrics_summary(24 * 7)
            
            report = {
                'generated_at': datetime.now().isoformat(),
                'database_path': self.db_path,
                'current_metrics': current_metrics.to_dict(),
                'alerts': alerts,
                'summary_24h': summary_24h,
                'summary_week': summary_week,
                'health_status': 'healthy' if not alerts else 'warning' if all(a['severity'] != 'critical' for a in alerts) else 'critical'
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Ошибка генерации отчета: {e}")
            return {'error': str(e)}
    
    def cleanup_old_metrics(self, days: int = 30):
        """Очистка старых файлов метрик"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for metrics_file in self.metrics_log_dir.glob("db_metrics_*.jsonl"):
            try:
                # Извлекаем дату из имени файла
                date_str = metrics_file.stem.split('_')[-1]
                file_date = datetime.strptime(date_str, "%Y%m%d")
                
                if file_date < cutoff_date:
                    metrics_file.unlink()
                    logger.info(f"Удален старый файл метрик: {metrics_file}")
                    
            except Exception as e:
                logger.error(f"Ошибка при очистке файла метрик {metrics_file}: {e}")


# Глобальный экземпляр монитора
db_monitor = DatabaseMonitor()


class QueryTimer:
    """Контекстный менеджер для измерения времени выполнения запросов"""
    
    def __init__(self, query_description: str = ""):
        self.query_description = query_description
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            query_time = time.time() - self.start_time
            db_monitor.record_query_time(query_time)
            
            if query_time > 1.0:  # Логируем медленные запросы
                logger.warning(f"Медленный запрос ({query_time:.2f}s): {self.query_description}")


# Декоратор для автоматического измерения времени запросов
def monitor_query(description: str = ""):
    """Декоратор для мониторинга времени выполнения запросов"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with QueryTimer(description or func.__name__):
                return await func(*args, **kwargs)
        return wrapper
    return decorator
