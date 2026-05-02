from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

# Clinical nutrition guidelines: ICMR, ADA, DASH, ESC, RDA India
CONDITION_ADJUSTMENTS = {
    "diabetes_t2": {
        "carb_pct": 0.40, "protein_pct": 0.30, "fat_pct": 0.30,
        "notes": "Low-GI carbs enforced. High protein for satiety and glucose control.",
    },
    "pcos": {
        "carb_pct": 0.35, "protein_pct": 0.35, "fat_pct": 0.30,
        "notes": "Carb quality > quantity. Anti-inflammatory fats. Inositol-rich foods.",
    },
    "hypertension": {
        "calorie_modifier": 0,
        "notes": "DASH diet. Sodium <1500mg/day enforced in recipe filter. High potassium foods.",
    },
    "high_cholesterol": {
        "fat_pct": 0.25, "protein_pct": 0.28, "carb_pct": 0.47,
        "notes": "Saturated fat <7% cal. Increase soluble fiber. Omega-3 rich foods.",
    },
    "thyroid_hypo": {
        "calorie_modifier": -150,
        "protein_pct": 0.30,
        "notes": "Reduced TDEE. Iodine + selenium foods. Avoid raw goitrogens (cabbage, broccoli).",
    },
    "thyroid_hyper": {
        "calorie_modifier": 200,
        "notes": "Increased TDEE. Calcium-rich foods. Avoid excess iodine.",
    },
    "anemia": {
        "protein_pct": 0.30,
        "notes": "Iron-rich foods paired with Vitamin C. Avoid tea/coffee with meals (blocks iron).",
    },
    "osteoporosis": {
        "protein_pct": 0.28,
        "notes": "High calcium + Vitamin D. Protein for bone matrix. Limit phosphoric acid foods.",
    },
    "ibs": {
        "notes": "Low-FODMAP foods prioritised. Small frequent meals. Soluble fiber, not insoluble.",
    },
    "kidney_disease": {
        "protein_pct": 0.15, "calorie_modifier": 0,
        "notes": "Restricted protein (0.6-0.8g/kg). Limit potassium + phosphorus. Low sodium.",
    },
    "fatty_liver": {
        "fat_pct": 0.20, "carb_pct": 0.45, "protein_pct": 0.35, "calorie_modifier": -300,
        "notes": "Caloric deficit. No refined carbs or saturated fats. No alcohol.",
    },
    "gerd": {
        "notes": "Small meals. Avoid spicy/acidic/fatty. No eating 3h before sleep.",
    },
    "weight_loss": {
        "calorie_modifier": -200, "protein_pct": 0.30,
        "notes": "Additional deficit. High protein preserves muscle mass.",
    },
    "high_protein": {
        "protein_pct": 0.35, "carb_pct": 0.40, "fat_pct": 0.25,
        "notes": "Elevated protein for muscle gain / athletic performance.",
    },
    "gut_friendly": {
        "notes": "Prebiotic + probiotic foods. Fermented foods. High fiber diversity.",
    },
}


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

    tdee = bmr * 1.375  # lightly active baseline

    # Goal base adjustment
    if goal == "weight_loss":
        calories = tdee - 300
    elif goal == "muscle_gain":
        calories = tdee + 300
    else:
        calories = tdee

    # Health condition calorie modifiers (applied before floor so floor is respected)
    for tag in health_tags:
        calories += CONDITION_ADJUSTMENTS.get(tag, {}).get("calorie_modifier", 0)

    calories = max(1200, round(calories))  # floor after all modifiers

    # Base macros
    carb_pct, protein_pct, fat_pct = 0.50, 0.25, 0.25

    # Apply condition overrides (later conditions in list take precedence)
    for tag in health_tags:
        adj = CONDITION_ADJUSTMENTS.get(tag, {})
        if "carb_pct" in adj:
            carb_pct = adj["carb_pct"]
        if "protein_pct" in adj:
            protein_pct = adj["protein_pct"]
        if "fat_pct" in adj:
            fat_pct = adj["fat_pct"]

    # Normalize in case of conflicting conditions
    total = carb_pct + protein_pct + fat_pct
    if abs(total - 1.0) > 0.01:
        carb_pct /= total
        protein_pct /= total
        fat_pct /= total

    return {
        "daily_calorie_target": calories,
        "daily_protein_target_g": round((calories * protein_pct) / 4, 1),
        "daily_carbs_target_g": round((calories * carb_pct) / 4, 1),
        "daily_fat_target_g": round((calories * fat_pct) / 9, 1),
    }


def get_condition_notes(health_tags: list[str]) -> list[str]:
    """Clinical nutrition notes for all active health conditions."""
    return [
        CONDITION_ADJUSTMENTS[tag]["notes"]
        for tag in health_tags
        if tag in CONDITION_ADJUSTMENTS and "notes" in CONDITION_ADJUSTMENTS[tag]
    ]


def score_macros(meals: list) -> float:
    return 0.0
