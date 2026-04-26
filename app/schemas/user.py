from pydantic import BaseModel
from typing import List, Optional

class UserBase(BaseModel):
    phone: str
    name: str

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int

    class Config:
        from_attributes = True

class UserProfile(BaseModel):
    id: str
    phone: str
    name: str
    age: Optional[int]
    gender: Optional[str]
    weight_kg: Optional[float]
    height_cm: Optional[float]
    bmi: Optional[float]
    bmi_band: Optional[str]
    goal: Optional[str]
    eating_mode: Optional[str]
    nv_days: List[str]
    health_tags: List[str]
    allergy_tags: List[str]
    cuisine_prefs: List[str]
    daily_calorie_target: Optional[int]
    household_id: Optional[str]
    is_household_head: bool
    wa_phone: Optional[str]
    wa_opted_in: bool
    timezone: str
    onboarding_complete: bool

    class Config:
        from_attributes = True

class UpdateBasicRequest(BaseModel):
    name: str
    age: int
    gender: str
    weight_kg: float
    height_cm: float

class UpdateHealthRequest(BaseModel):
    health_tags: List[str]
    allergy_tags: List[str]

class UpdateEatingRequest(BaseModel):
    eating_mode: str
    nv_days: List[str]
    cuisine_prefs: List[str]

class UpdateWhatsAppRequest(BaseModel):
    wa_phone: str