#!/usr/bin/env python3
"""
Production Health Monitor
Мониторинг состояния всех сервисов и автоматическое восстановление
"""
import asyncio
import os
import sys
import time
import logging
import json
import psutil
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Устанавливаем переменные окружения
os.environ["ENVIRONMENT"] = "production"
os.environ["PYTHONPATH"] = "/app"
os.environ["PYTHONUNBUFFERED"] = "1"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/health-monitor.log')
    ]
)
logger = logging.getLogger(__name__)

class ProductionHealthMonitor:
    """Монитор состояния production сервисов"""
    
    def __init__(self):
        self.check_interval = 60  # 1 минута
        self.health_history = []
        self.max_history = 100
        self.alert_thresholds = {
            "cpu_percent": 80,
            "memory_percent": 85,
            "disk_percent": 90,
            "response_time": 5.0  # секунд
        }
        
        # Эндпоинты для проверки
        self.endpoints = [
            {"name": "Admin Panel", "url": "http://127.0.0.1:8080/health", "critical": True},
            {"name": "Admin API", "url": "http://127.0.0.1:8080/api/health", "critical": True}
        ]
    
    async def check_system_resources(self) -> Dict[str, Any]:
        """Проверить системные ресурсы"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "status": "healthy"
            }
        except Exception as e:
            logger.error(f"Ошибка проверки системных ресурсов: {e}")
            return {"status": "error", "error": str(e)}
    
    async def check_database_health(self) -> Dict[str, Any]:
        """Проверить состояние базы данных"""
        try:
            from database.db_adapter import DatabaseAdapter
            
            database_url = os.getenv('DATABASE_URL')
            adapter = DatabaseAdapter(database_url)
            
            start_time = time.time()
            await adapter.connect()
            
            # Простой запрос для проверки
            result = await adapter.fetch_one("SELECT 1")
            
            await adapter.disconnect()
            response_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "response_time": round(response_time, 3),
                "database_type": adapter.db_type,
                "connection_successful": True
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки БД: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "connection_successful": False
            }
    
    async def check_endpoints(self) -> Dict[str, Any]:
        """Проверить HTTP эндпоинты"""
        results = {}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in self.endpoints:
                try:
                    start_time = time.time()
                    response = await client.get(endpoint["url"])
                    response_time = time.time() - start_time
                    
                    results[endpoint["name"]] = {
                        "status": "healthy" if response.status_code == 200 else "unhealthy",
                        "status_code": response.status_code,
                        "response_time": round(response_time, 3),
                        "critical": endpoint["critical"]
                    }
                    
                except Exception as e:
                    results[endpoint["name"]] = {
                        "status": "unhealthy",
                        "error": str(e),
                        "critical": endpoint["critical"]
                    }
        
        return results
    
    async def check_processes(self) -> Dict[str, Any]:
        """Проверить запущенные процессы"""
        try:
            processes = {
                "telegram_bot": False,
                "admin_panel": False,
                "migration_watcher": False,
                "data_sync": False
            }
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    
                    if 'main.py' in cmdline:
                        processes["telegram_bot"] = True
                    elif 'run_admin.py' in cmdline:
                        processes["admin_panel"] = True
                    elif 'production_migration_watcher.py' in cmdline:
                        processes["migration_watcher"] = True
                    elif 'production_data_sync.py' in cmdline:
                        processes["data_sync"] = True
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return {
                "status": "healthy" if all(processes.values()) else "warning",
                "processes": processes,
                "running_count": sum(processes.values()),
                "total_count": len(processes)
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки процессов: {e}")
            return {"status": "error", "error": str(e)}
    
    async def check_logs_health(self) -> Dict[str, Any]:
        """Проверить состояние логов"""
        try:
            log_dir = Path("/app/logs")
            log_files = list(log_dir.glob("*.log"))
            
            log_status = {}
            total_size = 0
            
            for log_file in log_files:
                try:
                    stat = log_file.stat()
                    size_mb = stat.st_size / (1024 * 1024)
                    total_size += size_mb
                    
                    # Проверяем, обновлялся ли лог в последние 10 минут
                    last_modified = datetime.fromtimestamp(stat.st_mtime)
                    is_recent = datetime.now() - last_modified < timedelta(minutes=10)
                    
                    log_status[log_file.name] = {
                        "size_mb": round(size_mb, 2),
                        "last_modified": last_modified.isoformat(),
                        "is_recent": is_recent
                    }
                    
                except Exception as e:
                    log_status[log_file.name] = {"error": str(e)}
            
            return {
                "status": "healthy",
                "total_size_mb": round(total_size, 2),
                "log_count": len(log_files),
                "logs": log_status
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки логов: {e}")
            return {"status": "error", "error": str(e)}
    
    async def perform_health_check(self) -> Dict[str, Any]:
        """Выполнить полную проверку состояния"""
        logger.info("🔍 Выполнение проверки состояния системы...")
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "checks": {}
        }
        
        # Выполняем все проверки
        checks = [
            ("system_resources", self.check_system_resources()),
            ("database", self.check_database_health()),
            ("endpoints", self.check_endpoints()),
            ("processes", self.check_processes()),
            ("logs", self.check_logs_health())
        ]
        
        for check_name, check_coro in checks:
            try:
                result = await check_coro
                health_report["checks"][check_name] = result
                
                # Определяем общий статус
                if result.get("status") == "unhealthy":
                    health_report["overall_status"] = "unhealthy"
                elif result.get("status") == "warning" and health_report["overall_status"] == "healthy":
                    health_report["overall_status"] = "warning"
                    
            except Exception as e:
                logger.error(f"Ошибка проверки {check_name}: {e}")
                health_report["checks"][check_name] = {"status": "error", "error": str(e)}
                health_report["overall_status"] = "unhealthy"
        
        # Сохраняем в историю
        self.health_history.append(health_report)
        if len(self.health_history) > self.max_history:
            self.health_history.pop(0)
        
        # Логируем результат
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️",
            "unhealthy": "❌",
            "error": "🚨"
        }
        
        emoji = status_emoji.get(health_report["overall_status"], "❓")
        logger.info(f"{emoji} Общий статус: {health_report['overall_status']}")
        
        return health_report
    
    async def save_health_report(self, report: Dict[str, Any]):
        """Сохранить отчет о состоянии"""
        try:
            reports_dir = Path("/app/data/health_reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            report_file = reports_dir / f"health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            
            # Очищаем старые отчеты (оставляем последние 24)
            report_files = sorted(reports_dir.glob("health_*.json"))
            if len(report_files) > 24:
                for old_report in report_files[:-24]:
                    old_report.unlink()
                    
        except Exception as e:
            logger.error(f"Ошибка сохранения отчета: {e}")
    
    async def run(self):
        """Основной цикл мониторинга"""
        logger.info("🔍 Запуск Production Health Monitor...")
        logger.info(f"⏱️ Интервал проверки: {self.check_interval} секунд")
        logger.info(f"📊 Пороги предупреждений: {self.alert_thresholds}")
        
        while True:
            try:
                # Выполняем проверку состояния
                health_report = await self.perform_health_check()
                
                # Сохраняем отчет
                await self.save_health_report(health_report)
                
                # Ждем до следующей проверки
                await asyncio.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("👋 Получен сигнал остановки")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(self.check_interval)

if __name__ == "__main__":
    try:
        monitor = ProductionHealthMonitor()
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        logger.info("👋 Health Monitor остановлен")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
