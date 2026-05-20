from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.recipe import RecipeOut


class SlotNutrition(BaseModel):
    """Per-slot recommended serving multiplier and scaled quantities."""
    multiplier: float = 1.0          # how many times the listed recipe to eat (1.0 = as served)
    recommended_qty: str = ""        # human-readable: "2x (4 pesarattu, ~680 kcal)"
    scaled_calories: int = 0


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
    # Raw totals (what 1× of each recipe provides)
    total_calories: Optional[int]
    total_protein_g: Optional[float]
    total_carbs_g: Optional[float]
    total_fat_g: Optional[float]
    # Per-slot serving guidance
    breakfast_serving: SlotNutrition = SlotNutrition()
    morning_snack_serving: SlotNutrition = SlotNutrition()
    lunch_serving: SlotNutrition = SlotNutrition()
    evening_snack_serving: SlotNutrition = SlotNutrition()
    dinner_serving: SlotNutrition = SlotNutrition()
    # Scaled daily totals (what you SHOULD eat to hit targets)
    target_calories: int = 0
    scaled_calories: int = 0
    scaled_protein_g: float = 0.0
    scaled_carbs_g: float = 0.0
    scaled_fat_g: float = 0.0
    scaled_fiber_g: float = 0.0
    # Nutrition balance warnings
    nutrition_warnings: list[str] = []
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


class GroceryItem(BaseModel):
    name: str
    qty: float
    unit: str


class GroceryListResponse(BaseModel):
    date: date
    items: list[GroceryItem]
    recipe_count: int
    member_count: int


class MenuInsightsResponse(BaseModel):
    signals_active: dict
    candidate_pool: dict[str, int]
    cuisine_used: str
    calorie_target: Optional[int]
    exclusion_window_7d: dict[str, int]
