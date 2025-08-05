"""
Система автоматических бэкапов для production-ready уровня
"""
import asyncio
import logging
import os
import shutil
import gzip
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import schedule
import threading
import time

logger = logging.getLogger(__name__)


class BackupSystem:
    """Система автоматических бэкапов"""
    
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # Настройки бэкапов
        self.daily_backups_keep = 7      # Дневные бэкапы хранить 7 дней
        self.weekly_backups_keep = 4     # Недельные бэкапы хранить 4 недели
        self.monthly_backups_keep = 12   # Месячные бэкапы хранить 12 месяцев
        
        # Сжатие бэкапов
        self.compress_backups = True
        
        # Статистика
        self.backup_stats = {
            'total_backups': 0,
            'successful_backups': 0,
            'failed_backups': 0,
            'last_backup': None,
            'last_error': None
        }
        
        self._scheduler_thread = None
        self._running = False
    
    def create_backup_filename(self, backup_type: str = "manual") -> str:
        """Создать имя файла бэкапа"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"bot_backup_{backup_type}_{timestamp}.db"
    
    async def create_backup(self, backup_type: str = "manual", compress: bool = None) -> Optional[str]:
        """Создать бэкап базы данных"""
        if compress is None:
            compress = self.compress_backups
        
        try:
            self.backup_stats['total_backups'] += 1
            
            # Проверяем существование исходной базы
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(f"База данных не найдена: {self.db_path}")
            
            # Создаем имя файла
            backup_filename = self.create_backup_filename(backup_type)
            backup_path = self.backup_dir / backup_filename
            
            # Копируем файл
            shutil.copy2(self.db_path, backup_path)
            
            # Проверяем целостность
            await self._verify_backup(backup_path)
            
            # Сжимаем если нужно
            if compress:
                compressed_path = await self._compress_backup(backup_path)
                backup_path.unlink()  # Удаляем несжатый файл
                backup_path = compressed_path
            
            # Обновляем статистику
            self.backup_stats['successful_backups'] += 1
            self.backup_stats['last_backup'] = datetime.now().isoformat()
            
            # Сохраняем метаданные
            await self._save_backup_metadata(backup_path, backup_type)
            
            logger.info(f"Бэкап создан: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            self.backup_stats['failed_backups'] += 1
            self.backup_stats['last_error'] = str(e)
            logger.error(f"Ошибка создания бэкапа: {e}")
            return None
    
    async def _verify_backup(self, backup_path: Path):
        """Проверить целостность бэкапа"""
        import sqlite3
        
        try:
            conn = sqlite3.connect(str(backup_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            
            if result[0] != "ok":
                raise Exception(f"Бэкап поврежден: {result[0]}")
                
        except Exception as e:
            logger.error(f"Ошибка проверки бэкапа: {e}")
            raise
    
    async def _compress_backup(self, backup_path: Path) -> Path:
        """Сжать бэкап"""
        compressed_path = backup_path.with_suffix('.db.gz')
        
        with open(backup_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        logger.debug(f"Бэкап сжат: {compressed_path}")
        return compressed_path
    
    async def _save_backup_metadata(self, backup_path: Path, backup_type: str):
        """Сохранить метаданные бэкапа"""
        metadata = {
            'backup_type': backup_type,
            'created_at': datetime.now().isoformat(),
            'original_db_path': self.db_path,
            'file_size': backup_path.stat().st_size,
            'compressed': backup_path.suffix == '.gz'
        }
        
        metadata_path = backup_path.with_suffix('.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    async def restore_backup(self, backup_path: str, target_path: Optional[str] = None) -> bool:
        """Восстановить базу данных из бэкапа"""
        if target_path is None:
            target_path = self.db_path
        
        try:
            backup_path = Path(backup_path)
            
            if not backup_path.exists():
                raise FileNotFoundError(f"Бэкап не найден: {backup_path}")
            
            # Создаем бэкап текущей базы перед восстановлением
            if os.path.exists(target_path):
                current_backup = await self.create_backup("pre_restore")
                logger.info(f"Создан бэкап текущей БД: {current_backup}")
            
            # Восстанавливаем
            if backup_path.suffix == '.gz':
                # Распаковываем сжатый бэкап
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(target_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # Копируем обычный бэкап
                shutil.copy2(backup_path, target_path)
            
            # Проверяем восстановленную базу
            await self._verify_backup(Path(target_path))
            
            logger.info(f"База данных восстановлена из бэкапа: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка восстановления из бэкапа: {e}")
            return False
    
    def cleanup_old_backups(self):
        """Очистка старых бэкапов по политике хранения"""
        now = datetime.now()
        
        # Получаем все бэкапы
        backups = []
        for backup_file in self.backup_dir.glob("bot_backup_*.db*"):
            if backup_file.suffix in ['.db', '.gz']:
                try:
                    # Извлекаем дату из имени файла
                    parts = backup_file.stem.split('_')
                    if len(parts) >= 4:
                        date_str = parts[3]  # YYYYMMDD
                        time_str = parts[4] if len(parts) > 4 else "000000"  # HHMMSS
                        backup_date = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                        
                        backups.append({
                            'path': backup_file,
                            'date': backup_date,
                            'type': parts[2] if len(parts) > 2 else 'manual'
                        })
                except:
                    continue
        
        # Сортируем по дате
        backups.sort(key=lambda x: x['date'], reverse=True)
        
        # Применяем политику хранения
        daily_cutoff = now - timedelta(days=self.daily_backups_keep)
        weekly_cutoff = now - timedelta(weeks=self.weekly_backups_keep)
        monthly_cutoff = now - timedelta(days=30 * self.monthly_backups_keep)
        
        for backup in backups:
            should_delete = False
            
            if backup['type'] == 'daily' and backup['date'] < daily_cutoff:
                should_delete = True
            elif backup['type'] == 'weekly' and backup['date'] < weekly_cutoff:
                should_delete = True
            elif backup['type'] == 'monthly' and backup['date'] < monthly_cutoff:
                should_delete = True
            elif backup['type'] == 'manual' and backup['date'] < monthly_cutoff:
                # Ручные бэкапы храним как месячные
                should_delete = True
            
            if should_delete:
                try:
                    backup['path'].unlink()
                    # Удаляем метаданные если есть
                    metadata_path = backup['path'].with_suffix('.json')
                    if metadata_path.exists():
                        metadata_path.unlink()
                    
                    logger.info(f"Удален старый бэкап: {backup['path']}")
                except Exception as e:
                    logger.error(f"Ошибка удаления бэкапа {backup['path']}: {e}")
    
    def get_backup_list(self) -> List[Dict]:
        """Получить список всех бэкапов"""
        backups = []
        
        for backup_file in self.backup_dir.glob("bot_backup_*.db*"):
            if backup_file.suffix in ['.db', '.gz']:
                try:
                    metadata_path = backup_file.with_suffix('.json')
                    metadata = {}
                    
                    if metadata_path.exists():
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                    
                    backups.append({
                        'path': str(backup_file),
                        'name': backup_file.name,
                        'size': backup_file.stat().st_size,
                        'created_at': metadata.get('created_at', 'Unknown'),
                        'backup_type': metadata.get('backup_type', 'Unknown'),
                        'compressed': metadata.get('compressed', backup_file.suffix == '.gz')
                    })
                except:
                    continue
        
        # Сортируем по дате создания
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        return backups
    
    def start_scheduler(self):
        """Запустить планировщик автоматических бэкапов"""
        if self._running:
            return

        # Останавливаем предыдущий поток если он существует
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self.stop_scheduler()
            time.sleep(1)  # Даем время на остановку

        # Настраиваем расписание
        schedule.clear()

        # Ежедневные бэкапы в 2:00
        schedule.every().day.at("02:00").do(self._scheduled_backup, "daily")

        # Еженедельные бэкапы по воскресеньям в 3:00
        schedule.every().sunday.at("03:00").do(self._scheduled_backup, "weekly")

        # Ежемесячные бэкапы 1 числа в 4:00
        schedule.every().month.do(self._scheduled_backup, "monthly")

        # Очистка старых бэкапов каждый день в 5:00
        schedule.every().day.at("05:00").do(self.cleanup_old_backups)

        self._running = True
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()

        logger.info("Планировщик автоматических бэкапов запущен")
    
    def stop_scheduler(self):
        """Остановить планировщик"""
        self._running = False
        schedule.clear()
        logger.info("Планировщик автоматических бэкапов остановлен")
    
    def _run_scheduler(self):
        """Запуск планировщика в отдельном потоке"""
        while self._running:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту
    
    def _scheduled_backup(self, backup_type: str):
        """Создать запланированный бэкап"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.create_backup(backup_type))
            loop.close()
        except Exception as e:
            logger.error(f"Ошибка запланированного бэкапа {backup_type}: {e}")
    
    def get_stats(self) -> Dict:
        """Получить статистику бэкапов"""
        return self.backup_stats.copy()


# Глобальный экземпляр системы бэкапов
backup_system = BackupSystem()
