"""
Сервис для логирования действий администраторов
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import aiosqlite

from database.universal_database import UniversalDatabase

logger = logging.getLogger(__name__)


class AuditService:
    """Сервис для аудита действий администраторов"""
    
    def __init__(self, db: UniversalDatabase):
        self.db = db
    
    async def log_action(
        self,
        admin_user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Логировать действие администратора
        
        Args:
            admin_user_id: ID администратора
            action: Действие (CREATE, UPDATE, DELETE, VIEW, etc.)
            resource_type: Тип ресурса (user, broadcast, role, etc.)
            resource_id: ID ресурса (опционально)
            details: Дополнительные детали действия
            ip_address: IP адрес администратора
            user_agent: User Agent браузера
            
        Returns:
            bool: Успешность логирования
        """
        try:
            async with aiosqlite.connect(self.db.db_path) as db:
                await db.execute("""
                    INSERT INTO audit_logs (
                        admin_user_id, action, resource_type, resource_id,
                        details, ip_address, user_agent, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    admin_user_id,
                    action,
                    resource_type,
                    resource_id,
                    json.dumps(details) if details else None,
                    ip_address,
                    user_agent,
                    datetime.now()
                ))
                await db.commit()
                
                logger.info(f"Audit log created: {action} on {resource_type} by admin {admin_user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            return False
    
    async def get_logs(
        self,
        admin_user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Получить логи действий
        
        Args:
            admin_user_id: Фильтр по администратору
            resource_type: Фильтр по типу ресурса
            action: Фильтр по действию
            limit: Лимит записей
            offset: Смещение
            
        Returns:
            List[Dict]: Список логов
        """
        try:
            conditions = []
            params = []
            
            if admin_user_id:
                conditions.append("al.admin_user_id = ?")
                params.append(admin_user_id)
            
            if resource_type:
                conditions.append("al.resource_type = ?")
                params.append(resource_type)
            
            if action:
                conditions.append("al.action = ?")
                params.append(action)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            async with aiosqlite.connect(self.db.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute(f"""
                    SELECT 
                        al.*,
                        au.username as admin_username,
                        au.email as admin_email
                    FROM audit_logs al
                    LEFT JOIN admin_users au ON al.admin_user_id = au.id
                    {where_clause}
                    ORDER BY al.created_at DESC
                    LIMIT ? OFFSET ?
                """, params + [limit, offset])
                
                rows = await cursor.fetchall()
                
                logs = []
                for row in rows:
                    log_dict = dict(row)
                    # Парсим JSON детали
                    if log_dict.get('details'):
                        try:
                            log_dict['details'] = json.loads(log_dict['details'])
                        except json.JSONDecodeError:
                            log_dict['details'] = {}
                    
                    logs.append(log_dict)
                
                return logs
                
        except Exception as e:
            logger.error(f"Failed to get audit logs: {e}")
            return []
    
    async def get_logs_count(
        self,
        admin_user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None
    ) -> int:
        """
        Получить количество логов
        
        Args:
            admin_user_id: Фильтр по администратору
            resource_type: Фильтр по типу ресурса
            action: Фильтр по действию
            
        Returns:
            int: Количество логов
        """
        try:
            conditions = []
            params = []
            
            if admin_user_id:
                conditions.append("admin_user_id = ?")
                params.append(admin_user_id)
            
            if resource_type:
                conditions.append("resource_type = ?")
                params.append(resource_type)
            
            if action:
                conditions.append("action = ?")
                params.append(action)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            async with aiosqlite.connect(self.db.db_path) as db:
                cursor = await db.execute(f"""
                    SELECT COUNT(*) as count
                    FROM audit_logs
                    {where_clause}
                """, params)
                
                row = await cursor.fetchone()
                return row[0] if row else 0
                
        except Exception as e:
            logger.error(f"Failed to get audit logs count: {e}")
            return 0
    
    async def get_admin_activity_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Получить статистику активности администраторов
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            List[Dict]: Статистика по администраторам
        """
        try:
            async with aiosqlite.connect(self.db.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute("""
                    SELECT 
                        al.admin_user_id,
                        au.username,
                        au.email,
                        COUNT(*) as total_actions,
                        COUNT(DISTINCT al.resource_type) as resource_types_count,
                        MAX(al.created_at) as last_activity
                    FROM audit_logs al
                    LEFT JOIN admin_users au ON al.admin_user_id = au.id
                    WHERE al.created_at >= datetime('now', '-{} days')
                    GROUP BY al.admin_user_id, au.username, au.email
                    ORDER BY total_actions DESC
                """.format(days))
                
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get admin activity stats: {e}")
            return []
    
    async def get_resource_activity_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Получить статистику активности по ресурсам
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            List[Dict]: Статистика по ресурсам
        """
        try:
            async with aiosqlite.connect(self.db.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute("""
                    SELECT 
                        resource_type,
                        action,
                        COUNT(*) as count
                    FROM audit_logs
                    WHERE created_at >= datetime('now', '-{} days')
                    GROUP BY resource_type, action
                    ORDER BY count DESC
                """.format(days))
                
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get resource activity stats: {e}")
            return []
    
    async def cleanup_old_logs(self, days: int = 90) -> int:
        """
        Очистить старые логи
        
        Args:
            days: Количество дней для хранения логов
            
        Returns:
            int: Количество удаленных записей
        """
        try:
            async with aiosqlite.connect(self.db.db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM audit_logs
                    WHERE created_at < datetime('now', '-{} days')
                """.format(days))
                
                await db.commit()
                deleted_count = cursor.rowcount
                
                logger.info(f"Cleaned up {deleted_count} old audit logs")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old audit logs: {e}")
            return 0


# Константы для типов действий
class AuditAction:
    """Константы для типов действий"""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    VIEW = "VIEW"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    SEND = "SEND"
    BLOCK = "BLOCK"
    UNBLOCK = "UNBLOCK"
    ROLE_CHANGE = "ROLE_CHANGE"


# Константы для типов ресурсов
class AuditResource:
    """Константы для типов ресурсов"""
    USER = "user"
    BROADCAST = "broadcast"
    TEMPLATE = "template"
    ROLE = "role"
    ADMIN_USER = "admin_user"
    SYSTEM = "system"
    STATISTICS = "statistics"


# Глобальный экземпляр сервиса (будет инициализирован в app.py)
audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """Получить экземпляр сервиса аудита"""
    if audit_service is None:
        raise RuntimeError("Audit service not initialized")
    return audit_service


def init_audit_service(db: UniversalDatabase) -> AuditService:
    """Инициализировать сервис аудита"""
    global audit_service
    audit_service = AuditService(db)
    return audit_service
