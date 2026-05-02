from collections import defaultdict


def build_grocery_list(recipes: dict, member_count: int = 1) -> list[dict]:
    """
    Aggregate ingredients from recipe slot dict into a consolidated grocery list.
    recipes: {slot_name: Recipe | None}
    member_count: scales ingredients marked per_person=True
    Returns sorted list of {name, qty, unit}
    """
    agg: dict[str, dict] = defaultdict(lambda: {"qty": 0.0, "unit": ""})

    for recipe in recipes.values():
        if not recipe:
            continue
        for ing in (recipe.ingredients or []):
            name = (ing.get("name") or "").lower().strip()
            if not name:
                continue
            mult = member_count if ing.get("per_person") else 1
            agg[name]["qty"] += float(ing.get("qty", 0)) * mult
            agg[name]["unit"] = ing.get("unit", "")

    result = []
    for name in sorted(agg):
        qty = agg[name]["qty"]
        unit = agg[name]["unit"]
        if unit == "g" and qty >= 1000:
            qty, unit = qty / 1000, "kg"
        elif unit == "ml" and qty >= 1000:
            qty, unit = qty / 1000, "l"
        if qty > 0:
            result.append({"name": name.title(), "qty": round(qty, 1), "unit": unit})

    return result
