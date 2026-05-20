from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.household_member import HouseholdMember

# Clinical nutrition guidelines: ICMR-NIN 2020, ADA, DASH, ESC, WHO
CONDITION_ADJUSTMENTS = {
    "diabetes_t2": {
        # Low-GI carbs enforced in recipe filter. Protein stays at ICMR weight-based value.
        # Carb quality > quantity — shift carb/fat split toward lower carb.
        "carb_split_override": 0.55,  # of remaining calories after protein
        "fat_split_override": 0.45,
        "notes": "Low-GI carbs enforced. Reduce refined carbs. Carb quality drives glucose control, not protein ratio.",
    },
    "pcos": {
        "carb_split_override": 0.52,
        "fat_split_override": 0.48,
        "notes": "Low-GI enforcement in recipe filter. Anti-inflammatory fats (omega-3, olive oil). Inositol-rich foods.",
    },
    "hypertension": {
        "calorie_modifier": 0,
        "notes": "DASH diet. Sodium <1500mg/day enforced in recipe filter. High potassium foods.",
    },
    "high_cholesterol": {
        "carb_split_override": 0.62,
        "fat_split_override": 0.38,
        "notes": "Saturated fat <7% cal. Increase soluble fiber. Omega-3 rich foods.",
    },
    "thyroid_hypo": {
        "calorie_modifier": -150,
        "notes": "Reduced TDEE. Iodine + selenium foods. Avoid raw goitrogens (cabbage, broccoli).",
    },
    "thyroid_hyper": {
        "calorie_modifier": 200,
        "notes": "Increased TDEE. Calcium-rich foods. Avoid excess iodine.",
    },
    "anemia": {
        "notes": "Iron-rich foods paired with Vitamin C. Avoid tea/coffee with meals (blocks iron absorption).",
    },
    "osteoporosis": {
        # Bone matrix needs adequate protein — bump to 1.0g/kg floor
        "protein_g_per_kg_override": 1.0,
        "notes": "High calcium + Vitamin D. Adequate protein for bone matrix. Limit phosphoric acid foods.",
    },
    "ibs": {
        "notes": "Low-FODMAP foods prioritised. Small frequent meals. Soluble fiber, not insoluble.",
    },
    "kidney_disease": {
        # Hard clinical override: 0.6g/kg (ICMR renal guideline)
        "protein_g_per_kg_override": 0.6,
        "calorie_modifier": 0,
        "notes": "Restricted protein (0.6g/kg). Limit potassium + phosphorus. Low sodium.",
    },
    "fatty_liver": {
        "calorie_modifier": -300,
        "protein_g_per_kg_override": 1.2,  # higher protein for satiety during deficit
        "carb_split_override": 0.55,
        "fat_split_override": 0.45,
        "notes": "Caloric deficit. No refined carbs or saturated fats. No alcohol.",
    },
    "gerd": {
        "notes": "Small meals. Avoid spicy/acidic/fatty. No eating 3h before sleep.",
    },
    "weight_loss": {
        "calorie_modifier": -200,
        "protein_g_per_kg_override": 1.0,  # preserve muscle during deficit
        "notes": "Additional deficit. Adequate protein preserves muscle mass.",
    },
    "high_protein": {
        # Explicit user intent: bodybuilder / athlete
        "protein_g_per_kg_override": 1.4,
        "notes": "Elevated protein for muscle gain / athletic performance.",
    },
    "gut_friendly": {
        "notes": "Prebiotic + probiotic foods. Fermented foods. High fiber diversity.",
    },
}

# ICMR-NIN 2020 protein recommendations (g per kg body weight)
PROTEIN_G_PER_KG = {
    "sedentary":         0.8,
    "lightly_active":    1.0,
    "moderately_active": 1.2,
    "active":            1.4,
}

# PAL multipliers for TDEE from BMR
ACTIVITY_MULTIPLIERS = {
    "sedentary":         1.2,
    "lightly_active":    1.375,
    "moderately_active": 1.55,
    "active":            1.725,
}

# Carb/fat split of remaining calories after protein — by primary cuisine
# South Indian diets are rice-heavy (high carb), Kerala is coconut-heavy (high fat),
# Punjabi/North Indian has more dairy fat
CUISINE_MACRO_SPLIT = {
    "andhra":       {"carb": 0.65, "fat": 0.35},
    "tamil":        {"carb": 0.65, "fat": 0.35},
    "karnataka":    {"carb": 0.62, "fat": 0.38},
    "south_indian": {"carb": 0.65, "fat": 0.35},
    "kerala":       {"carb": 0.55, "fat": 0.45},
    "goan":         {"carb": 0.55, "fat": 0.45},
    "punjabi":      {"carb": 0.52, "fat": 0.48},
    "north_indian": {"carb": 0.58, "fat": 0.42},
    "bengali":      {"carb": 0.60, "fat": 0.40},
    "maharashtrian":{"carb": 0.60, "fat": 0.40},
    "gujarati":     {"carb": 0.60, "fat": 0.40},
    "hyderabadi":   {"carb": 0.55, "fat": 0.45},
    "rajasthani":   {"carb": 0.58, "fat": 0.42},
    "sattvic":      {"carb": 0.60, "fat": 0.40},
    "default":      {"carb": 0.60, "fat": 0.40},
}


def calculate_targets(user: "Union[User, HouseholdMember]", cuisine_pref: str | None = None) -> dict:
    weight = float(user.weight_kg or 70)
    height = float(user.height_cm or 170)
    age = int(user.age or 30)
    gender = (user.gender or "male").lower()
    goal = (user.goal or "maintenance").lower()
    health_tags = user.health_tags or []
    activity_level = (user.activity_level or "lightly_active").lower()

    # Mifflin-St Jeor BMR
    if gender == "male":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    # TDEE with activity-appropriate multiplier
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.375)
    tdee = bmr * multiplier

    # Goal base adjustment
    if goal == "weight_loss":
        calories = tdee - 300
    elif goal == "muscle_gain":
        calories = tdee + 300
    else:
        calories = tdee

    # Health condition calorie modifiers
    for tag in health_tags:
        calories += CONDITION_ADJUSTMENTS.get(tag, {}).get("calorie_modifier", 0)

    calories = max(1200, round(calories))

    # Protein: ICMR weight-based formula
    base_protein_per_kg = PROTEIN_G_PER_KG.get(activity_level, 1.0)
    protein_g_per_kg = base_protein_per_kg

    # Health condition protein overrides (hard clinical limits take precedence)
    for tag in health_tags:
        override = CONDITION_ADJUSTMENTS.get(tag, {}).get("protein_g_per_kg_override")
        if override is not None:
            # For kidney disease (restriction), always use the lowest. For others, take highest.
            if tag == "kidney_disease":
                protein_g_per_kg = min(protein_g_per_kg, override)
            else:
                protein_g_per_kg = max(protein_g_per_kg, override)

    protein_g = round(weight * protein_g_per_kg, 1)
    protein_cal = protein_g * 4

    # Remaining calories go to carbs and fat
    remaining_cal = max(0, calories - protein_cal)

    # Carb/fat split by cuisine, then overridden by applicable health conditions
    cuisine_key = cuisine_pref or "default"
    split = CUISINE_MACRO_SPLIT.get(cuisine_key, CUISINE_MACRO_SPLIT["default"])
    carb_ratio = split["carb"]
    fat_ratio = split["fat"]

    for tag in health_tags:
        adj = CONDITION_ADJUSTMENTS.get(tag, {})
        if "carb_split_override" in adj:
            carb_ratio = adj["carb_split_override"]
            fat_ratio = adj["fat_split_override"]

    carb_g = round((remaining_cal * carb_ratio) / 4, 1)
    fat_g = round((remaining_cal * fat_ratio) / 9, 1)

    return {
        "daily_calorie_target": calories,
        "daily_protein_target_g": protein_g,
        "daily_carbs_target_g": carb_g,
        "daily_fat_target_g": fat_g,
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
