"""
Nutrition balance engine.

Calculates per-slot serving multipliers so the day's meals actually hit
the user's calorie, protein, carb, fat and fiber targets. Also generates
human-readable nutrition warnings when the day is significantly unbalanced.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.recipe import Recipe

SLOT_RATIOS: dict[str, float] = {
    "breakfast":     0.25,
    "morning_snack": 0.10,
    "lunch":         0.35,
    "evening_snack": 0.10,
    "dinner":        0.20,
}

# ICMR-NIN 2020 daily minimums for adults
FIBER_MIN_G   = 25.0    # g/day
IRON_MIN_MG   = 9.0     # mg/day (men); women need 17mg but we use conservative min
CALCIUM_MIN_MG = 600.0  # mg/day


def _round_to_half(x: float) -> float:
    """Round to nearest 0.5 — gives practical serving guidance (1.0, 1.5, 2.0 …)."""
    return round(x * 2) / 2


def _build_recommended_qty(recipe: "Recipe", multiplier: float, slot_target_cal: float) -> str:
    """Return a concise human string: '×2 (4 pesarattu · ~680 kcal)'."""
    if multiplier <= 1.05:
        return ""   # close enough — no adjustment needed
    scaled_cal = int(recipe.calories * multiplier)
    suffix = f"~{scaled_cal} kcal"
    # Try to scale the serving_unit quantity if it contains a count
    if recipe.serving_unit:
        su = recipe.serving_unit
        scaled_su = _scale_serving_unit(su, multiplier)
        if scaled_su and scaled_su != su:
            return f"×{multiplier:.1f} ({scaled_su} · {suffix})"
    return f"×{multiplier:.1f} serving · {suffix}"


def _scale_serving_unit(serving_unit: str, multiplier: float) -> str:
    """
    Attempt to scale numeric quantities in a serving_unit string.
    '2 crepes' × 2 → '4 crepes'
    '1 bowl dal (240ml) with 1 roti' × 1.5 → '1½ bowls dal (360ml) with 2 rotis'
    Falls back to the original string if parsing is ambiguous.
    """
    import re

    def scale_num(n: float, m: float) -> str:
        result = n * m
        if result == int(result):
            return str(int(result))
        # Express as fraction for common halves
        if abs(result - int(result) - 0.5) < 0.01:
            return f"{int(result)}½"
        return f"{result:.1f}".rstrip("0").rstrip(".")

    # Replace all numeric quantities in the string.
    # Use negative lookbehind so we don't match mid-word numbers,
    # but DO match "240" in "(240ml)" — hence no trailing \b requirement.
    def replacer(match):
        try:
            num = float(match.group(1))
        except ValueError:
            return match.group()
        return scale_num(num, multiplier)

    scaled = re.sub(r'(?<![.\w])(\d+(?:\.\d+)?)', replacer, serving_unit)
    return scaled if scaled != serving_unit else ""


def compute_slot_serving(
    recipe: "Recipe",
    slot: str,
    calorie_target: int,
) -> dict:
    """
    Compute the recommended serving multiplier for a single slot.
    Returns a dict matching SlotNutrition fields.
    """
    if not recipe or not recipe.calories:
        return {"multiplier": 1.0, "recommended_qty": "", "scaled_calories": 0}

    slot_target_cal = calorie_target * SLOT_RATIOS.get(slot, 0.20)
    raw_multiplier = slot_target_cal / recipe.calories

    # Only suggest a multiplier when significantly off (>15% under or >20% over)
    if raw_multiplier < 1.15:
        multiplier = 1.0
    else:
        multiplier = _round_to_half(raw_multiplier)
        multiplier = max(1.0, multiplier)

    scaled_cal = int(recipe.calories * multiplier)
    recommended_qty = _build_recommended_qty(recipe, multiplier, slot_target_cal)

    return {
        "multiplier": multiplier,
        "recommended_qty": recommended_qty,
        "scaled_calories": scaled_cal,
    }


def compute_daily_balance(
    recipes: dict,             # slot_name → Recipe | None
    slot_servings: dict,       # slot_name → {"multiplier": float, ...}
    calorie_target: int,
    protein_target_g: float,
    carbs_target_g: float,
    fat_target_g: float,
) -> dict:
    """
    Compute scaled daily nutrition totals (applying multipliers) and
    generate clinical nutrition warnings if targets are missed.
    """
    scaled_cal   = 0
    scaled_prot  = 0.0
    scaled_carbs = 0.0
    scaled_fat   = 0.0
    scaled_fiber = 0.0
    scaled_iron  = 0.0
    scaled_calc  = 0.0

    for slot, recipe in recipes.items():
        if not recipe:
            continue
        m = slot_servings.get(slot, {}).get("multiplier", 1.0)
        scaled_cal   += int((recipe.calories or 0) * m)
        scaled_prot  += float(recipe.protein_g or 0) * m
        scaled_carbs += float(recipe.carbs_g   or 0) * m
        scaled_fat   += float(recipe.fat_g     or 0) * m
        scaled_fiber += float(recipe.fibre_g   or 0) * m
        scaled_iron  += float(recipe.iron_mg   or 0) * m
        scaled_calc  += float(recipe.calcium_mg or 0) * m

    warnings: list[str] = []

    cal_pct = scaled_cal / calorie_target if calorie_target else 1.0
    if cal_pct < 0.80:
        warnings.append(
            f"Calorie target not met — {scaled_cal} kcal vs {calorie_target} kcal goal. "
            f"Consider eating the recommended portions or adding a healthy snack."
        )

    if protein_target_g and scaled_prot < protein_target_g * 0.75:
        warnings.append(
            f"Low protein — {scaled_prot:.0f}g vs {protein_target_g:.0f}g goal. "
            f"Add eggs, curd, dal, or lean meat to boost intake."
        )

    if carbs_target_g and scaled_carbs < carbs_target_g * 0.60:
        warnings.append(
            f"Low carbohydrates — {scaled_carbs:.0f}g vs {carbs_target_g:.0f}g goal. "
            f"Eat the full recommended rice/roti portion."
        )

    if scaled_fiber < FIBER_MIN_G:
        warnings.append(
            f"Low fiber — {scaled_fiber:.1f}g vs 25g ICMR minimum. "
            f"Add a raw salad, vegetable, or fruit to each main meal."
        )

    if scaled_iron < IRON_MIN_MG:
        warnings.append(
            f"Low iron — include gongura, dark leafy greens, or sesame seeds daily."
        )

    if scaled_calc < CALCIUM_MIN_MG:
        warnings.append(
            f"Low calcium — add curd/buttermilk (perugu/majjiga) or sesame seeds to meals."
        )

    return {
        "scaled_calories":  scaled_cal,
        "scaled_protein_g": round(scaled_prot,  1),
        "scaled_carbs_g":   round(scaled_carbs, 1),
        "scaled_fat_g":     round(scaled_fat,   1),
        "scaled_fiber_g":   round(scaled_fiber, 1),
        "nutrition_warnings": warnings,
    }
