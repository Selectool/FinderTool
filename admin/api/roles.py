"""
API endpoints для управления ролями пользователей
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse

from ..auth.permissions import get_current_active_user, log_admin_action, RequireUserEdit
from ..auth.models import TokenData
from ..models.user_models import (
    RoleChangeRequest, BulkRoleChangeRequest, RoleStatsResponse, UserRoleInfo
)
from ..decorators.audit_decorator import audit_role_action, audit_system_action
from ..services.audit_service import AuditAction
from database.universal_database import UniversalDatabase

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_db(request: Request) -> Database:
    """Получить объект базы данных"""
    return request.state.db


@router.get("/stats", response_model=List[RoleStatsResponse])
@audit_system_action(AuditAction.VIEW)
async def get_role_statistics(
    db: UniversalDatabase = Depends(get_db),
    current_user: TokenData = Depends(RequireUserEdit)
):
    """Получить статистику по ролям"""
    try:
        from bot.utils.roles import TelegramUserRole, TelegramUserPermissions
        
        stats = []
        total_users = 0
        
        # Подсчитываем пользователей по каждой роли
        role_counts = {}
        for role in TelegramUserRole:
            users = await db.get_users_by_role(role.value)
            count = len(users)
            role_counts[role.value] = count
            total_users += count
        
        # Формируем статистику
        for role, count in role_counts.items():
            percentage = (count / total_users * 100) if total_users > 0 else 0
            stats.append(RoleStatsResponse(
                role=role,
                role_display_name=TelegramUserPermissions.get_role_display_name(role),
                user_count=count,
                percentage=round(percentage, 2)
            ))
        
        # Сортируем по количеству пользователей
        stats.sort(key=lambda x: x.user_count, reverse=True)
        
        await log_admin_action(
            current_user.user_id,
            "VIEW_ROLE_STATS",
            f"Viewed role statistics"
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики ролей: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения статистики ролей"
        )


@router.get("/user/{user_id}", response_model=UserRoleInfo)
async def get_user_role_info(
    user_id: int,
    db: UniversalDatabase = Depends(get_db),
    current_user: TokenData = Depends(RequireUserEdit)
):
    """Получить информацию о роли пользователя"""
    try:
        from bot.utils.roles import TelegramUserPermissions, RoleHierarchy, TelegramUserRole
        
        # Получаем данные пользователя
        user_data = await db.get_user(user_id)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )
        
        current_role = await db.get_user_role(user_id)
        
        # Определяем роли, на которые можно изменить
        can_change_to = []
        current_admin_role = current_user.role
        
        for role in TelegramUserRole:
            if RoleHierarchy.can_manage_role(current_admin_role, role.value):
                can_change_to.append(role.value)
        
        user_info = UserRoleInfo(
            user_id=user_id,
            username=user_data.get('username'),
            first_name=user_data.get('first_name'),
            last_name=user_data.get('last_name'),
            current_role=current_role,
            role_display_name=TelegramUserPermissions.get_role_display_name(current_role),
            can_change_to=can_change_to,
            unlimited_access=TelegramUserPermissions.has_unlimited_access(user_id, current_role),
            is_admin=TelegramUserPermissions.is_admin(user_id, current_role),
            created_at=user_data['created_at'],
            last_request=user_data.get('last_request')
        )
        
        await log_admin_action(
            current_user.user_id,
            "VIEW_USER_ROLE",
            f"Viewed role info for user {user_id}"
        )
        
        return user_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения информации о роли пользователя {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения информации о пользователе"
        )


@router.post("/change")
@audit_role_action(AuditAction.ROLE_CHANGE, resource_id_param="user_id")
async def change_user_role(
    request: RoleChangeRequest,
    db: UniversalDatabase = Depends(get_db),
    current_user: TokenData = Depends(RequireUserEdit)
):
    """Изменить роль пользователя"""
    try:
        from bot.utils.roles import RoleHierarchy, TelegramUserRole, TelegramUserPermissions
        
        # Проверяем, что роль существует
        valid_roles = [role.value for role in TelegramUserRole]
        if request.new_role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недопустимая роль"
            )
        
        # Проверяем права на изменение роли
        if not RoleHierarchy.can_manage_role(current_user.role, request.new_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для назначения этой роли"
            )
        
        # Проверяем, существует ли пользователь
        user_data = await db.get_user(request.user_id)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )
        
        # Получаем текущую роль
        current_role = await db.get_user_role(request.user_id)
        
        # Проверяем, может ли администратор изменить текущую роль пользователя
        if not RoleHierarchy.can_manage_role(current_user.role, current_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для изменения роли этого пользователя"
            )
        
        # Обновляем роль
        success = await db.update_user_role(request.user_id, request.new_role)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при обновлении роли"
            )
        
        # Логируем действие
        await log_admin_action(
            current_user.user_id,
            "CHANGE_USER_ROLE",
            f"Changed user {request.user_id} role from {current_role} to {request.new_role}. Reason: {request.reason or 'Not specified'}"
        )
        
        role_display = TelegramUserPermissions.get_role_display_name(request.new_role)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": f"Роль пользователя успешно изменена на {role_display}",
                "user_id": request.user_id,
                "new_role": request.new_role,
                "new_role_display": role_display
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка изменения роли пользователя {request.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при изменении роли"
        )


@router.post("/bulk-change")
async def bulk_change_roles(
    request: BulkRoleChangeRequest,
    db: UniversalDatabase = Depends(get_db),
    current_user: TokenData = Depends(RequireUserEdit)
):
    """Массовое изменение ролей пользователей"""
    try:
        from bot.utils.roles import RoleHierarchy, TelegramUserRole, TelegramUserPermissions
        
        # Проверяем, что роль существует
        valid_roles = [role.value for role in TelegramUserRole]
        if request.new_role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недопустимая роль"
            )
        
        # Проверяем права на изменение роли
        if not RoleHierarchy.can_manage_role(current_user.role, request.new_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для назначения этой роли"
            )
        
        successful_changes = 0
        failed_changes = 0
        errors = []
        
        for user_id in request.user_ids:
            try:
                # Проверяем, существует ли пользователь
                user_data = await db.get_user(user_id)
                if not user_data:
                    errors.append(f"Пользователь {user_id} не найден")
                    failed_changes += 1
                    continue
                
                # Получаем текущую роль
                current_role = await db.get_user_role(user_id)
                
                # Проверяем права на изменение текущей роли
                if not RoleHierarchy.can_manage_role(current_user.role, current_role):
                    errors.append(f"Нет прав для изменения роли пользователя {user_id}")
                    failed_changes += 1
                    continue
                
                # Обновляем роль
                success = await db.update_user_role(user_id, request.new_role)
                
                if success:
                    successful_changes += 1
                else:
                    errors.append(f"Ошибка обновления роли пользователя {user_id}")
                    failed_changes += 1
                    
            except Exception as e:
                logger.error(f"Ошибка изменения роли пользователя {user_id}: {e}")
                errors.append(f"Ошибка для пользователя {user_id}: {str(e)}")
                failed_changes += 1
        
        # Логируем действие
        await log_admin_action(
            current_user.user_id,
            "BULK_CHANGE_ROLES",
            f"Bulk changed {successful_changes} users to role {request.new_role}. Failed: {failed_changes}. Reason: {request.reason or 'Not specified'}"
        )
        
        role_display = TelegramUserPermissions.get_role_display_name(request.new_role)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": f"Массовое изменение ролей завершено",
                "successful_changes": successful_changes,
                "failed_changes": failed_changes,
                "new_role": request.new_role,
                "new_role_display": role_display,
                "errors": errors
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка массового изменения ролей: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при массовом изменении ролей"
        )


@router.get("/available")
async def get_available_roles(
    current_user: TokenData = Depends(RequireUserEdit)
):
    """Получить список доступных ролей для назначения"""
    try:
        from bot.utils.roles import TelegramUserRole, TelegramUserPermissions, RoleHierarchy
        
        available_roles = []
        
        for role in TelegramUserRole:
            if RoleHierarchy.can_manage_role(current_user.role, role.value):
                available_roles.append({
                    "value": role.value,
                    "display_name": TelegramUserPermissions.get_role_display_name(role.value),
                    "level": RoleHierarchy.get_role_level(role.value)
                })
        
        # Сортируем по уровню
        available_roles.sort(key=lambda x: x["level"])
        
        return available_roles
        
    except Exception as e:
        logger.error(f"Ошибка получения доступных ролей: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения доступных ролей"
        )
