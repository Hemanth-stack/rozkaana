from datetime import datetime, date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


VALID_GENDERS = {"male", "female", "other"}
VALID_GOALS = {"weight_loss", "maintenance", "muscle_gain"}
VALID_EATING_MODES = {"jain", "sattvic", "pure_veg", "conditional_nv", "full_nv"}
VALID_CUISINES = {
    "north_indian", "south_indian", "bengali", "gujarati", "maharashtrian",
    "punjabi", "hyderabadi", "rajasthani", "kerala", "goan", "sattvic",
    "andhra", "tamil", "karnataka",
    "chinese", "italian", "continental",
}

VALID_ACTIVITY_LEVELS = {"sedentary", "lightly_active", "moderately_active", "active"}
VALID_DINNER_STYLES = {"rice_plate", "tiffin", "roti_based", "mixed"}


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
    email: Optional[str] = None
    email_verified: Optional[bool] = False
    household_id: Optional[UUID]
    is_household_head: Optional[bool] = False
    activity_level: Optional[str] = None
    dinner_style_pref: Optional[str] = None
    wa_phone: Optional[str]
    wa_opted_in: Optional[bool] = False
    onboarding_complete: Optional[bool] = False
    is_admin: Optional[bool] = False
    is_active: Optional[bool] = True
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


class UpdateBasicRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    age: Optional[int] = Field(None, ge=1, le=120)
    gender: Optional[str] = None
    weight_kg: Optional[float] = Field(None, ge=20.0, le=500.0)
    height_cm: Optional[float] = Field(None, ge=50.0, le=300.0)
    activity_level: Optional[str] = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v is not None and v.lower() not in VALID_GENDERS:
            raise ValueError(f"gender must be one of: {VALID_GENDERS}")
        return v.lower() if v else v

    @field_validator("activity_level")
    @classmethod
    def validate_activity_level(cls, v):
        if v is not None and v not in VALID_ACTIVITY_LEVELS:
            raise ValueError(f"activity_level must be one of: {VALID_ACTIVITY_LEVELS}")
        return v


class UpdateHealthRequest(BaseModel):
    health_tags: Optional[list[str]] = None
    allergy_tags: Optional[list[str]] = None


class UpdateEatingRequest(BaseModel):
    eating_mode: Optional[str] = None
    nv_days: Optional[list[str]] = None
    cuisine_prefs: Optional[list[str]] = None
    dinner_style_pref: Optional[str] = None

    @field_validator("eating_mode")
    @classmethod
    def validate_eating_mode(cls, v):
        if v is not None and v not in VALID_EATING_MODES:
            raise ValueError(f"eating_mode must be one of: {VALID_EATING_MODES}")
        return v

    @field_validator("cuisine_prefs")
    @classmethod
    def validate_cuisine_prefs(cls, v):
        if v:
            invalid = [c for c in v if c not in VALID_CUISINES]
            if invalid:
                raise ValueError(f"Invalid cuisines: {invalid}. Valid: {sorted(VALID_CUISINES)}")
        return v

    @field_validator("dinner_style_pref")
    @classmethod
    def validate_dinner_style_pref(cls, v):
        if v is not None and v not in VALID_DINNER_STYLES:
            raise ValueError(f"dinner_style_pref must be one of: {VALID_DINNER_STYLES}")
        return v


class UpdateGoalRequest(BaseModel):
    goal: str

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v):
        if v not in VALID_GOALS:
            raise ValueError(f"goal must be one of: {VALID_GOALS}")
        return v


class UpdateWhatsAppRequest(BaseModel):
    wa_phone: str = Field(..., min_length=10, max_length=15)


class NutritionSignalRequest(BaseModel):
    energy_level: Optional[int] = Field(None, ge=1, le=10)
    hunger_rating: Optional[int] = Field(None, ge=1, le=10)
    digestion_comfort: Optional[int] = Field(None, ge=1, le=10)
    sleep_quality: Optional[int] = Field(None, ge=1, le=10)
    sleep_hours: Optional[float] = Field(None, ge=0.0, le=24.0)
    mood: Optional[str] = Field(None, max_length=20)
    focus_level: Optional[int] = Field(None, ge=1, le=10)
    blood_sugar_dip: Optional[bool] = None
    muscle_cramps: Optional[bool] = None
    hair_loss_noticed: Optional[bool] = None
    weight_kg: Optional[float] = Field(None, ge=20.0, le=500.0)
    blood_glucose_mg_dl: Optional[int] = Field(None, ge=50, le=600)
    followed_menu: Optional[bool] = None
    skipped_slots: Optional[list[str]] = None
    notes: Optional[str] = Field(None, max_length=500)


class NutritionSignalResponse(BaseModel):
    id: UUID
    user_id: UUID
    signal_date: date
    energy_level: Optional[int] = None
    hunger_rating: Optional[int] = None
    digestion_comfort: Optional[int] = None
    sleep_quality: Optional[int] = None
    sleep_hours: Optional[float] = None
    mood: Optional[str] = None
    focus_level: Optional[int] = None
    blood_sugar_dip: Optional[bool] = None
    muscle_cramps: Optional[bool] = None
    hair_loss_noticed: Optional[bool] = None
    weight_kg: Optional[float] = None
    blood_glucose_mg_dl: Optional[int] = None
    followed_menu: Optional[bool] = None
    skipped_slots: Optional[list[str]] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# Legacy aliases
UserCreate = UpdateBasicRequest
User = UserProfile
