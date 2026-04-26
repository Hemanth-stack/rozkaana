from pydantic import BaseModel
from typing import List
from .recipe import Recipe
from .user import UserProfile

class RecipeListResponse(BaseModel):
    recipes: List[Recipe]

class CreateRecipeRequest(BaseModel):
    name: str
    name_local: Optional[str]
    meal_type: str
    cuisine_region: str
    eating_mode_tags: List[str]
    health_safe_tags: List[str]
    allergy_free_tags: List[str]
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fibre_g: float
    serving_unit: str
    prep_time_mins: int
    spice_level: str
    main_ingredient: str
    ingredients: dict
    steps: List[str]

class VerifyRecipeRequest(BaseModel):
    pass

class GenerateBatchResponse(BaseModel):
    task_id: str

class UserListResponse(BaseModel):
    users: List[UserProfile]