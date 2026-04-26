from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class RecipeIngredient(BaseModel):
    name: str
    qty: float
    unit: str
    per_person: bool = False


class RecipeCreate(BaseModel):
    name: str
    name_local: Optional[str] = None
    meal_type: str
    cuisine_region: str
    eating_mode_tags: list[str]
    health_safe_tags: list[str] = []
    allergy_free_tags: list[str] = []
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fibre_g: Optional[float] = None
    serving_unit: Optional[str] = None
    prep_time_mins: Optional[int] = None
    spice_level: Optional[str] = None
    main_ingredient: Optional[str] = None
    ingredients: Optional[list[dict[str, Any]]] = None
    steps: Optional[list[str]] = None

    @field_validator("calories")
    @classmethod
    def calories_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("calories must be > 0")
        return v

    @field_validator("protein_g")
    @classmethod
    def protein_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("protein_g must be >= 0")
        return v


class RecipeUpdate(BaseModel):
    name: Optional[str] = None
    name_local: Optional[str] = None
    meal_type: Optional[str] = None
    cuisine_region: Optional[str] = None
    eating_mode_tags: Optional[list[str]] = None
    health_safe_tags: Optional[list[str]] = None
    allergy_free_tags: Optional[list[str]] = None
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fibre_g: Optional[float] = None
    serving_unit: Optional[str] = None
    prep_time_mins: Optional[int] = None
    spice_level: Optional[str] = None
    main_ingredient: Optional[str] = None
    ingredients: Optional[list[dict[str, Any]]] = None
    steps: Optional[list[str]] = None
    is_active: Optional[bool] = None


class RecipeOut(BaseModel):
    id: UUID
    name: str
    name_local: Optional[str]
    meal_type: str
    cuisine_region: str
    eating_mode_tags: list[str]
    health_safe_tags: Optional[list[str]]
    allergy_free_tags: Optional[list[str]]
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fibre_g: Optional[float]
    serving_unit: Optional[str]
    prep_time_mins: Optional[int]
    spice_level: Optional[str]
    main_ingredient: Optional[str]
    ingredients: Optional[list[dict[str, Any]]]
    steps: Optional[list[str]]
    is_verified: bool
    is_active: bool
    source: Optional[str]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


# Legacy aliases used by older code
Recipe = RecipeOut
RecipeBase = RecipeCreate
