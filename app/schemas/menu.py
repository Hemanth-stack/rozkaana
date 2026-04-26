from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.recipe import RecipeOut


class MenuResponse(BaseModel):
    id: UUID
    owner_id: UUID
    owner_type: str
    menu_date: date
    breakfast: Optional[RecipeOut] = None
    morning_snack: Optional[RecipeOut] = None
    lunch: Optional[RecipeOut] = None
    evening_snack: Optional[RecipeOut] = None
    dinner: Optional[RecipeOut] = None
    total_calories: Optional[int]
    total_protein_g: Optional[float]
    total_carbs_g: Optional[float]
    total_fat_g: Optional[float]
    cuisine_override: Optional[str]
    is_regenerated: bool = False
    pdf_url: Optional[str]
    wa_status: Optional[str]

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    menus: list[MenuResponse]


class RegenRequest(BaseModel):
    cuisine_override: Optional[str] = None


class RegenerateResponse(BaseModel):
    task_id: str
    message: str


class TaskStatusResponse(BaseModel):
    status: str
    menu_date: Optional[str] = None
    error: Optional[str] = None


class OverrideCuisineRequest(BaseModel):
    cuisine: str


class PDFURLResponse(BaseModel):
    pdf_url: str
    expires_in_hours: int
