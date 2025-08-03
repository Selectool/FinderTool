"""
API endpoints для аутентификации
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer

from ..auth.models import UserLogin, Token, RefreshToken, UserResponse, PasswordChange
from ..auth.auth import authenticate_user, create_tokens, verify_token, get_password_hash
from ..auth.permissions import get_current_active_user, log_admin_action
from database.universal_database import UniversalDatabase

router = APIRouter()
security = HTTPBearer()


async def get_db(request: Request) -> UniversalDatabase:
    """Получить объект базы данных"""
    return request.state.db


@router.post("/login", response_model=Token)
async def login(
    user_credentials: UserLogin,
    request: Request,
    db: UniversalDatabase = Depends(get_db)
):
    """Вход в систему"""
    user = await authenticate_user(db, user_credentials.username, user_credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Аккаунт деактивирован",
        )
    
    # Создаем токены
    tokens = create_tokens(user)
    
    # Логируем вход
    await db.log_admin_action(
        admin_user_id=user["id"],
        action="login",
        resource_type="auth",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return tokens


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: RefreshToken,
    db: UniversalDatabase = Depends(get_db)
):
    """Обновление токена"""
    token_data = verify_token(refresh_data.refresh_token, token_type="refresh")
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный refresh токен",
        )
    
    # Получаем пользователя из базы
    user = await db.get_admin_user_by_username(token_data.username)
    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или деактивирован",
        )
    
    # Создаем новые токены
    tokens = create_tokens(user)
    
    return tokens


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_active_user),
    db: UniversalDatabase = Depends(get_db)
):
    """Получить информацию о текущем пользователе"""
    user = await db.get_admin_user_by_username(current_user.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return UserResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        is_active=user["is_active"],
        created_at=user["created_at"],
        last_login=user["last_login"]
    )


@router.post("/change-password")
@log_admin_action("change_password", "auth")
async def change_password(
    password_data: PasswordChange,
    current_user = Depends(get_current_active_user),
    db: UniversalDatabase = Depends(get_db)
):
    """Смена пароля"""
    # Получаем пользователя из базы
    user = await db.get_admin_user_by_username(current_user.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Проверяем текущий пароль
    from ..auth.auth import verify_password
    if not verify_password(password_data.current_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль"
        )
    
    # Обновляем пароль
    new_password_hash = get_password_hash(password_data.new_password)
    
    # Обновляем пароль в базе данных
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute(
            "UPDATE admin_users SET password_hash = ? WHERE id = ?",
            (new_password_hash, user["id"])
        )
        await conn.commit()
    
    return {"message": "Пароль успешно изменен"}


@router.post("/logout")
@log_admin_action("logout", "auth")
async def logout(
    current_user = Depends(get_current_active_user),
    db: UniversalDatabase = Depends(get_db)
):
    """Выход из системы"""
    # В простой реализации JWT токены не отзываются
    # В production можно добавить blacklist токенов
    
    return {"message": "Успешный выход из системы"}
