"""
Система прав доступа для рассылок
"""
from fastapi import HTTPException, Depends
from typing import Optional

from .permissions import get_current_user
from .models import TokenData
from database.universal_database import UniversalDatabase


class BroadcastPermissions:
    """Класс для проверки прав доступа к рассылкам"""

    def __init__(self, db: UniversalDatabase):
        self.db = db
        self._permissions_cache = {}  # Кэш прав пользователей
        self._cache_ttl = 300  # 5 минут
    
    async def _get_user_permissions_cached(self, user_id: int) -> list:
        """Получить права пользователя с кэшированием"""
        import time

        cache_key = f"user_{user_id}"
        current_time = time.time()

        # Проверяем кэш
        if cache_key in self._permissions_cache:
            cached_data = self._permissions_cache[cache_key]
            if current_time - cached_data['timestamp'] < self._cache_ttl:
                return cached_data['permissions']

        # Получаем права из БД
        permissions = await self.db.get_user_permissions(user_id)

        # Сохраняем в кэш
        self._permissions_cache[cache_key] = {
            'permissions': permissions,
            'timestamp': current_time
        }

        return permissions

    async def can_view_broadcasts(self, user: TokenData) -> bool:
        """Может ли пользователь просматривать рассылки"""
        if user.role in ['admin', 'super_admin']:
            return True

        # Проверяем специальные права
        user_permissions = await self._get_user_permissions_cached(user.user_id)
        return 'broadcasts_view' in user_permissions
    
    async def can_create_broadcasts(self, user: TokenData) -> bool:
        """Может ли пользователь создавать рассылки"""
        if user.role in ['admin', 'super_admin']:
            return True

        user_permissions = await self._get_user_permissions_cached(user.user_id)
        return 'broadcasts_create' in user_permissions

    async def can_send_broadcasts(self, user: TokenData) -> bool:
        """Может ли пользователь отправлять рассылки"""
        if user.role in ['admin', 'super_admin']:
            return True

        user_permissions = await self._get_user_permissions_cached(user.user_id)
        return 'broadcasts_send' in user_permissions

    async def can_manage_broadcasts(self, user: TokenData) -> bool:
        """Может ли пользователь управлять рассылками (приостанавливать, удалять)"""
        if user.role in ['admin', 'super_admin']:
            return True

        user_permissions = await self._get_user_permissions_cached(user.user_id)
        return 'broadcasts_manage' in user_permissions

    async def can_manage_templates(self, user: TokenData) -> bool:
        """Может ли пользователь управлять шаблонами"""
        if user.role in ['admin', 'super_admin']:
            return True

        user_permissions = await self._get_user_permissions_cached(user.user_id)
        return 'templates_manage' in user_permissions


# Dependency функции для FastAPI
async def get_db() -> Database:
    """Получить объект базы данных"""
    return UniversalDatabase()


async def RequireBroadcastView(
    current_user: TokenData = Depends(get_current_user),
    db: UniversalDatabase = Depends(get_db)
) -> TokenData:
    """Требует права на просмотр рассылок"""
    permissions = BroadcastPermissions(db)
    
    if not await permissions.can_view_broadcasts(current_user):
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав для просмотра рассылок"
        )
    
    return current_user


async def RequireBroadcastCreate(
    current_user: TokenData = Depends(get_current_user),
    db: UniversalDatabase = Depends(get_db)
) -> TokenData:
    """Требует права на создание рассылок"""
    permissions = BroadcastPermissions(db)
    
    if not await permissions.can_create_broadcasts(current_user):
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав для создания рассылок"
        )
    
    return current_user


async def RequireBroadcastSend(
    current_user: TokenData = Depends(get_current_user),
    db: UniversalDatabase = Depends(get_db)
) -> TokenData:
    """Требует права на отправку рассылок"""
    permissions = BroadcastPermissions(db)
    
    if not await permissions.can_send_broadcasts(current_user):
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав для отправки рассылок"
        )
    
    return current_user


async def RequireBroadcastManage(
    current_user: TokenData = Depends(get_current_user),
    db: UniversalDatabase = Depends(get_db)
) -> TokenData:
    """Требует права на управление рассылками"""
    permissions = BroadcastPermissions(db)
    
    if not await permissions.can_manage_broadcasts(current_user):
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав для управления рассылками"
        )
    
    return current_user


async def RequireTemplateManage(
    current_user: TokenData = Depends(get_current_user),
    db: UniversalDatabase = Depends(get_db)
) -> TokenData:
    """Требует права на управление шаблонами"""
    permissions = BroadcastPermissions(db)
    
    if not await permissions.can_manage_templates(current_user):
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав для управления шаблонами"
        )
    
    return current_user


# Права доступа по умолчанию для ролей
DEFAULT_ROLE_PERMISSIONS = {
    'super_admin': [
        'broadcasts_view',
        'broadcasts_create', 
        'broadcasts_send',
        'broadcasts_manage',
        'templates_manage'
    ],
    'admin': [
        'broadcasts_view',
        'broadcasts_create',
        'broadcasts_send', 
        'broadcasts_manage',
        'templates_manage'
    ],
    'moderator': [
        'broadcasts_view',
        'broadcasts_create',
        'templates_manage'
    ],
    'user': [
        'broadcasts_view'
    ]
}


async def init_broadcast_permissions(db: UniversalDatabase):
    """Инициализировать права доступа для рассылок"""
    try:
        import aiosqlite

        # Проверяем, существует ли уже таблица
        async with aiosqlite.connect(db.db_path) as conn:
            cursor = await conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='user_permissions'
            """)
            table_exists = await cursor.fetchone()

            if table_exists:
                # Таблица уже существует, пропускаем инициализацию
                return

            # Создаем таблицу прав доступа
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    permission TEXT NOT NULL,
                    granted_by INTEGER,
                    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES admin_users (id),
                    FOREIGN KEY (granted_by) REFERENCES admin_users (id),
                    UNIQUE(user_id, permission)
                )
            """)

            # Создаем индекс для быстрого поиска
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_permissions_user_id
                ON user_permissions (user_id)
            """)

            await conn.commit()
            print("Система прав доступа для рассылок инициализирована")

    except Exception as e:
        print(f"Ошибка инициализации прав доступа: {e}")


async def grant_permissions_to_user(db: UniversalDatabase, user_id: int, permissions: list, granted_by: int = None):
    """Предоставить права пользователю"""
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        for permission in permissions:
            try:
                await conn.execute("""
                    INSERT OR IGNORE INTO user_permissions (user_id, permission, granted_by)
                    VALUES (?, ?, ?)
                """, (user_id, permission, granted_by))
            except Exception as e:
                print(f"Ошибка предоставления права {permission} пользователю {user_id}: {e}")

        await conn.commit()


async def revoke_permissions_from_user(db: UniversalDatabase, user_id: int, permissions: list):
    """Отозвать права у пользователя"""
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        for permission in permissions:
            await conn.execute("""
                DELETE FROM user_permissions
                WHERE user_id = ? AND permission = ?
            """, (user_id, permission))

        await conn.commit()


async def get_user_permissions(db: UniversalDatabase, user_id: int) -> list:
    """Получить список прав пользователя"""
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        cursor = await conn.execute("""
            SELECT permission FROM user_permissions WHERE user_id = ?
        """, (user_id,))

        rows = await cursor.fetchall()
        return [row[0] for row in rows]


# Добавляем метод в класс Database
def add_get_user_permissions_method():
    """Добавить метод get_user_permissions в класс Database"""
    import aiosqlite

    async def get_user_permissions(self, user_id: int) -> list:
        """Получить список прав пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Проверяем, является ли пользователь админом
                cursor = await db.execute("""
                    SELECT role FROM admin_users WHERE id = ?
                """, (user_id,))

                row = await cursor.fetchone()
                if row and row[0] in ['admin', 'super_admin']:
                    # Админы имеют все права
                    return ['broadcast_view', 'broadcast_create', 'broadcast_send', 'broadcast_manage']

                # Пытаемся получить права из таблицы user_permissions
                cursor = await db.execute("""
                    SELECT permission FROM user_permissions WHERE user_id = ?
                """, (user_id,))

                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        except Exception:
            # Если таблица не существует, возвращаем пустой список
            return []

    # Динамически добавляем метод в класс UniversalDatabase
    from database.universal_database import UniversalDatabase
    UniversalDatabase.get_user_permissions = get_user_permissions
