import base64
import os
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    from app.models.daily_menu import DailyMenu
    from app.models.recipe import Recipe
    from app.models.user import User

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))


def render_menu_pdf(menu: "DailyMenu", members: list["User"], recipes: dict[str, "Recipe | None"]) -> bytes:
    template = _env.get_template("meal_plan.html")

    slots_def = [
        ("breakfast", "Breakfast", "8:00 AM"),
        ("morning_snack", "Morning Snack", "10:30 AM"),
        ("lunch", "Lunch", "1:00 PM"),
        ("evening_snack", "Evening Snack", "4:30 PM"),
        ("dinner", "Dinner", "8:00 PM"),
    ]

    slots = []
    for key, label, time_str in slots_def:
        recipe = recipes.get(f"{key}_id")
        if recipe:
            slots.append({"key": key, "label": label, "time": time_str, "recipe": recipe})

    daily_totals = _calc_totals(recipes)
    grocery = _build_grocery_list(recipes, len(members)) if len(members) > 1 else []

    ctx = {
        "date": menu.menu_date.strftime("%A, %d %B %Y"),
        "slots": slots,
        "daily_totals": daily_totals,
        "grocery_list": grocery,
        "members": members,
        "is_household": len(members) > 1,
        "logo_base64": _load_logo_b64(),
    }

    html_str = template.render(**ctx)
    from weasyprint import HTML
    return HTML(string=html_str, base_url=str(_TEMPLATE_DIR)).write_pdf()


def _calc_totals(recipes: dict) -> dict:
    return {
        "calories": sum(r.calories or 0 for r in recipes.values() if r),
        "protein": round(sum(float(r.protein_g or 0) for r in recipes.values() if r), 1),
        "carbs": round(sum(float(r.carbs_g or 0) for r in recipes.values() if r), 1),
        "fat": round(sum(float(r.fat_g or 0) for r in recipes.values() if r), 1),
        "fibre": round(sum(float(r.fibre_g or 0) for r in recipes.values() if r), 1),
    }


def _build_grocery_list(recipes: dict, member_count: int) -> list[dict]:
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
    for name, val in sorted(agg.items()):
        qty = val["qty"]
        unit = val["unit"]
        if unit == "g" and qty >= 1000:
            qty = qty / 1000
            unit = "kg"
        result.append({"name": name.title(), "qty": round(qty, 1), "unit": unit})
    return result


def _load_logo_b64() -> str:
    logo_path = _TEMPLATE_DIR.parent / "static" / "logo.png"
    if logo_path.exists():
        return base64.b64encode(logo_path.read_bytes()).decode()
    return ""
