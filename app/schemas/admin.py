from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.recipe import RecipeOut, RecipeCreate
from app.schemas.user import UserProfile


class RecipeListResponse(BaseModel):
    recipes: list[RecipeOut]
    total: int
    page: int = 1
    limit: int = 20


class CreateRecipeRequest(RecipeCreate):
    pass


class GenerateBatchRequest(BaseModel):
    meal_type: str
    cuisine_region: str
    eating_mode: str
    health_tags: list[str] = []
    count: int = 5
    model: str = "claude-sonnet-4-6"


class GenerateBatchResponse(BaseModel):
    generated: int
    recipes: list[RecipeOut]


class UserAdminProfile(BaseModel):
    id: UUID
    name: Optional[str]
    email: Optional[str]
    phone: str
    eating_mode: Optional[str]
    goal: Optional[str]
    bmi: Optional[float]
    health_tags: Optional[list[str]] = []
    is_active: bool = True
    is_admin: bool = False
    onboarding_complete: bool = False
    wa_opted_in: bool = False
    created_at: Optional[datetime]
    plan_type: Optional[str] = None
    sub_status: Optional[str] = None
    sub_period_end: Optional[date] = None
    trial_end: Optional[date] = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserAdminProfile]
    total: int
    page: int = 1
    limit: int = 20


class DashboardStats(BaseModel):
    total_users: int
    active_subscribers: int
    menus_today: int
    pdfs_built_today: int
    wa_delivered_today: int
    wa_failed_today: int
    emails_sent_today: int = 0
    mrr: float
    plan_distribution: dict[str, int]


class PipelineStep(BaseModel):
    name: str
    count: int
    completed: int
    failed: int
    status: str


class PipelineStatus(BaseModel):
    date: date
    steps: list[PipelineStep]


class MenuAdminItem(BaseModel):
    id: UUID
    owner_id: UUID
    owner_type: str
    menu_date: date
    pdf_key: Optional[str]
    wa_status: Optional[str]
    wa_sent_at: Optional[datetime]
    generated_at: Optional[datetime]
    owner_name: Optional[str] = None

    model_config = {"from_attributes": True}


class MenuAdminListResponse(BaseModel):
    menus: list[MenuAdminItem]
    total: int


class ComponentHealth(BaseModel):
    status: str                    # "ok" | "degraded" | "down"
    latency_ms: Optional[float] = None
    detail: Optional[str] = None


class SystemHealthResponse(BaseModel):
    overall: str
    components: dict[str, ComponentHealth]
    checked_at: datetime
