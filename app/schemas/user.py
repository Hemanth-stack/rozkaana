from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class UserProfile(BaseModel):
    id: UUID
    phone: str
    name: Optional[str]
    age: Optional[int]
    gender: Optional[str]
    weight_kg: Optional[float]
    height_cm: Optional[float]
    bmi: Optional[float]
    bmi_band: Optional[str]
    goal: Optional[str]
    eating_mode: Optional[str]
    nv_days: Optional[list[str]] = []
    health_tags: Optional[list[str]] = []
    allergy_tags: Optional[list[str]] = []
    cuisine_prefs: Optional[list[str]] = []
    daily_calorie_target: Optional[int]
    daily_protein_target_g: Optional[float]
    daily_carbs_target_g: Optional[float]
    daily_fat_target_g: Optional[float]
    household_id: Optional[UUID]
    is_household_head: Optional[bool] = False
    wa_phone: Optional[str]
    wa_opted_in: Optional[bool] = False
    onboarding_complete: Optional[bool] = False
    is_admin: Optional[bool] = False
    is_active: Optional[bool] = True
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


class UpdateBasicRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None


class UpdateHealthRequest(BaseModel):
    health_tags: Optional[list[str]] = None
    allergy_tags: Optional[list[str]] = None


class UpdateEatingRequest(BaseModel):
    eating_mode: Optional[str] = None
    nv_days: Optional[list[str]] = None
    cuisine_prefs: Optional[list[str]] = None


class UpdateGoalRequest(BaseModel):
    goal: str


class UpdateWhatsAppRequest(BaseModel):
    wa_phone: str


# Legacy alias
UserCreate = UpdateBasicRequest
User = UserProfile
