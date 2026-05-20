from datetime import datetime, date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

VALID_MEMBER_TYPES   = {"adult", "teen", "child", "infant", "senior"}
VALID_GENDERS        = {"male", "female", "other"}
VALID_EATING_MODES   = {"jain", "sattvic", "pure_veg", "conditional_nv", "full_nv"}
VALID_GOALS          = {"weight_loss", "maintenance", "muscle_gain"}
VALID_ACTIVITY_LEVELS = {"sedentary", "lightly_active", "moderately_active", "active"}


class HouseholdMemberCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    member_type: str
    age: Optional[int] = Field(None, ge=0, le=120)
    gender: Optional[str] = None
    weight_kg: Optional[float] = Field(None, ge=1.0, le=300.0)
    height_cm: Optional[float] = Field(None, ge=30.0, le=250.0)
    eating_mode: Optional[str] = None
    activity_level: Optional[str] = None
    health_tags: Optional[list[str]] = []
    allergy_tags: Optional[list[str]] = []
    goal: Optional[str] = None

    @field_validator("member_type")
    @classmethod
    def validate_member_type(cls, v):
        if v not in VALID_MEMBER_TYPES:
            raise ValueError(f"member_type must be one of: {VALID_MEMBER_TYPES}")
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v is not None and v.lower() not in VALID_GENDERS:
            raise ValueError(f"gender must be one of: {VALID_GENDERS}")
        return v.lower() if v else v

    @field_validator("eating_mode")
    @classmethod
    def validate_eating_mode(cls, v):
        if v is not None and v not in VALID_EATING_MODES:
            raise ValueError(f"eating_mode must be one of: {VALID_EATING_MODES}")
        return v

    @field_validator("activity_level")
    @classmethod
    def validate_activity_level(cls, v):
        if v is not None and v not in VALID_ACTIVITY_LEVELS:
            raise ValueError(f"activity_level must be one of: {VALID_ACTIVITY_LEVELS}")
        return v

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v):
        if v is not None and v not in VALID_GOALS:
            raise ValueError(f"goal must be one of: {VALID_GOALS}")
        return v


class HouseholdMemberUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    member_type: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=120)
    gender: Optional[str] = None
    weight_kg: Optional[float] = Field(None, ge=1.0, le=300.0)
    height_cm: Optional[float] = Field(None, ge=30.0, le=250.0)
    eating_mode: Optional[str] = None
    activity_level: Optional[str] = None
    health_tags: Optional[list[str]] = None
    allergy_tags: Optional[list[str]] = None
    goal: Optional[str] = None

    @field_validator("member_type")
    @classmethod
    def validate_member_type(cls, v):
        if v is not None and v not in VALID_MEMBER_TYPES:
            raise ValueError(f"member_type must be one of: {VALID_MEMBER_TYPES}")
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v is not None and v.lower() not in VALID_GENDERS:
            raise ValueError(f"gender must be one of: {VALID_GENDERS}")
        return v.lower() if v else v

    @field_validator("eating_mode")
    @classmethod
    def validate_eating_mode(cls, v):
        if v is not None and v not in VALID_EATING_MODES:
            raise ValueError(f"eating_mode must be one of: {VALID_EATING_MODES}")
        return v

    @field_validator("activity_level")
    @classmethod
    def validate_activity_level(cls, v):
        if v is not None and v not in VALID_ACTIVITY_LEVELS:
            raise ValueError(f"activity_level must be one of: {VALID_ACTIVITY_LEVELS}")
        return v

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v):
        if v is not None and v not in VALID_GOALS:
            raise ValueError(f"goal must be one of: {VALID_GOALS}")
        return v


class HouseholdMemberResponse(BaseModel):
    id: UUID
    household_id: UUID
    linked_user_id: Optional[UUID] = None
    is_registered_user: bool = False        # True when linked_user_id is set
    name: str
    member_type: str
    age: Optional[int] = None
    gender: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    bmi: Optional[float] = None
    bmi_band: Optional[str] = None
    eating_mode: Optional[str] = None
    activity_level: Optional[str] = None
    health_tags: Optional[list[str]] = []
    allergy_tags: Optional[list[str]] = []
    goal: Optional[str] = None
    daily_calorie_target: Optional[int] = None
    daily_protein_target_g: Optional[float] = None
    daily_carbs_target_g: Optional[float] = None
    daily_fat_target_g: Optional[float] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_flags(cls, member):
        data = cls.model_validate(member)
        data.is_registered_user = member.linked_user_id is not None
        return data


class MemberSignalCreate(BaseModel):
    signal_date: Optional[date] = None       # defaults to today server-side
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
    weight_kg: Optional[float] = Field(None, ge=1.0, le=300.0)
    blood_glucose_mg_dl: Optional[int] = Field(None, ge=50, le=600)
    followed_menu: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=500)


class MemberSignalResponse(BaseModel):
    id: UUID
    member_id: UUID
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
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
