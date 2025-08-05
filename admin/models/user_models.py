"""
Модели данных для пользователей
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserFilterType(str, Enum):
    """Типы фильтров пользователей"""
    all = "all"
    active = "active"
    subscribed = "subscribed"
    unlimited = "unlimited"
    blocked = "blocked"
    bot_blocked = "bot_blocked"
    new_today = "new_today"
    new_week = "new_week"


class UserResponse(BaseModel):
    """Модель ответа с информацией о пользователе"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    created_at: datetime
    requests_used: int = 0
    is_subscribed: bool = False
    subscription_end: Optional[datetime] = None
    last_request: Optional[datetime] = None
    role: str = "user"
    unlimited_access: bool = False
    notes: Optional[str] = None
    blocked: bool = False
    bot_blocked: bool = False
    blocked_at: Optional[datetime] = None
    blocked_by: Optional[int] = None
    referrer_id: Optional[int] = None
    registration_source: str = "bot"
    
    @property
    def full_name(self) -> str:
        """Полное имя пользователя"""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) or self.username or f"User {self.user_id}"
    
    @property
    def subscription_status(self) -> str:
        """Статус подписки"""
        if self.unlimited_access:
            return "unlimited"
        elif self.is_subscribed and self.subscription_end:
            if datetime.now() < self.subscription_end:
                return "active"
            else:
                return "expired"
        return "none"

    @property
    def user_status(self) -> str:
        """Общий статус пользователя"""
        if self.blocked:
            return "blocked"
        elif self.bot_blocked:
            return "bot_blocked"
        elif self.unlimited_access:
            return "unlimited"
        elif self.is_subscribed and self.subscription_end and datetime.now() < self.subscription_end:
            return "subscribed"
        else:
            return "active"

    @property
    def status_display(self) -> str:
        """Отображаемый статус пользователя"""
        status_map = {
            "blocked": "Заблокирован",
            "bot_blocked": "Заблокировал бота",
            "unlimited": "Безлимитный",
            "subscribed": "Подписчик",
            "active": "Активный"
        }
        return status_map.get(self.user_status, "Неизвестно")


class UsersListResponse(BaseModel):
    """Модель ответа со списком пользователей"""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    pages: int
    filters_applied: dict


class UserUpdateRequest(BaseModel):
    """Модель запроса на обновление пользователя"""
    unlimited_access: Optional[bool] = None
    blocked: Optional[bool] = None
    notes: Optional[str] = None


class SubscriptionUpdateRequest(BaseModel):
    """Модель запроса на обновление подписки"""
    months: int = Field(gt=0, le=12, description="Количество месяцев подписки")
    action: str = Field(pattern="^(activate|extend|deactivate)$", description="Действие с подпиской")


class UserStatsResponse(BaseModel):
    """Модель ответа со статистикой пользователя"""
    user_id: int
    total_requests: int
    requests_today: int
    requests_week: int
    requests_month: int
    first_request: Optional[datetime] = None
    last_request: Optional[datetime] = None
    favorite_channels: List[str] = []
    subscription_history: List[dict] = []


class BulkActionRequest(BaseModel):
    """Модель запроса на массовые действия"""
    user_ids: List[int] = Field(min_items=1, max_items=100)
    action: str = Field(pattern="^(block|unblock|delete|grant_unlimited|revoke_unlimited)$")
    notes: Optional[str] = None


class UserExportRequest(BaseModel):
    """Модель запроса на экспорт пользователей"""
    format: str = Field(pattern="^(csv|xlsx)$", default="csv")
    filter_type: Optional[UserFilterType] = None
    search: Optional[str] = None
    include_stats: bool = False
    include_requests: bool = False


class UserSearchRequest(BaseModel):
    """Модель запроса поиска пользователей"""
    query: str = Field(min_length=1, max_length=100)
    search_in: List[str] = Field(default=["username", "first_name", "last_name", "user_id"])
    limit: int = Field(default=20, le=100)


class UserActivityResponse(BaseModel):
    """Модель ответа с активностью пользователя"""
    user_id: int
    date: datetime
    action: str
    details: Optional[dict] = None
    ip_address: Optional[str] = None


class UserNotificationRequest(BaseModel):
    """Модель запроса на отправку уведомления пользователю"""
    user_ids: List[int] = Field(min_items=1, max_items=1000)
    message: str = Field(min_length=1, max_length=4096)
    parse_mode: str = Field(default="HTML", pattern="^(HTML|Markdown)$")
    disable_notification: bool = False


class UserSegmentResponse(BaseModel):
    """Модель ответа с сегментами пользователей"""
    segment_name: str
    count: int
    percentage: float
    description: str


class UserAnalyticsResponse(BaseModel):
    """Модель ответа с аналитикой пользователей"""
    total_users: int
    active_users: int
    new_users_today: int
    new_users_week: int
    new_users_month: int
    subscribers: int
    unlimited_users: int
    blocked_users: int
    segments: List[UserSegmentResponse]
    growth_rate: float
    retention_rate: float


class RoleChangeRequest(BaseModel):
    """Запрос на изменение роли пользователя"""
    user_id: int
    new_role: str
    reason: Optional[str] = None


class BulkRoleChangeRequest(BaseModel):
    """Запрос на массовое изменение ролей"""
    user_ids: List[int]
    new_role: str
    reason: Optional[str] = None


class RoleStatsResponse(BaseModel):
    """Статистика по ролям"""
    role: str
    role_display_name: str
    user_count: int
    percentage: float


class UserRoleInfo(BaseModel):
    """Информация о роли пользователя"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    current_role: str
    role_display_name: str
    can_change_to: List[str]  # Роли, на которые можно изменить
    unlimited_access: bool
    is_admin: bool
    created_at: datetime
    last_request: Optional[datetime] = None
