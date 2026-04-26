from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User


def calculate_targets(user: "User") -> dict:
    weight = float(user.weight_kg or 70)
    height = float(user.height_cm or 170)
    age = int(user.age or 30)
    gender = (user.gender or "male").lower()
    goal = (user.goal or "maintenance").lower()
    health_tags = user.health_tags or []

    # Mifflin-St Jeor BMR
    if gender == "male":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    tdee = bmr * 1.375  # lightly active

    # Goal adjustments
    if goal == "weight_loss":
        calories = tdee - 300
    elif goal == "muscle_gain":
        calories = tdee + 300
    else:
        calories = tdee

    calories = max(1200, round(calories))

    # Medical overrides
    carb_pct = 0.50
    protein_pct = 0.25
    fat_pct = 0.25

    if "diabetes_t2" in health_tags:
        carb_pct = 0.40
        protein_pct = 0.30
        fat_pct = 0.30

    if "pcos" in health_tags:
        carb_pct = max(0.35, carb_pct - 0.15)
        protein_pct = min(0.35, protein_pct + 0.10)
        fat_pct = 1.0 - carb_pct - protein_pct

    protein_g = round((calories * protein_pct) / 4, 1)
    carbs_g = round((calories * carb_pct) / 4, 1)
    fat_g = round((calories * fat_pct) / 9, 1)

    return {
        "daily_calorie_target": calories,
        "daily_protein_target_g": protein_g,
        "daily_carbs_target_g": carbs_g,
        "daily_fat_target_g": fat_g,
    }


def score_macros(meals: list) -> float:
    return 0.0
