from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
from collections import defaultdict
from typing import List
import base64
import os

env = Environment(loader=FileSystemLoader("app/templates"))

def render_menu_pdf(menu, members: List, recipes: dict) -> bytes:
    template = env.get_template("meal_plan.html")
    ctx = {
        "date": menu.menu_date.strftime("%A, %d %B %Y"),
        "slots": _build_slots(menu, recipes),
        "daily_totals": _calc_totals(recipes),
        "grocery_list": _build_grocery_list(recipes, members),
        "members": members,
        "is_household": len(members) > 1,
        "logo_base64": _load_logo_b64(),
    }

    html_str = template.render(**ctx)
    pdf_bytes = HTML(string=html_str).write_pdf(
        stylesheets=[CSS(string=_load_inline_css())]
    )
    return pdf_bytes


def _build_slots(menu, recipes: dict):
    slot_map = [
        ("breakfast", "Breakfast", "8:00 AM"),
        ("morning_snack", "Morning Snack", "10:30 AM"),
        ("lunch", "Lunch", "1:00 PM"),
        ("evening_snack", "Evening Snack", "4:30 PM"),
        ("dinner", "Dinner", "8:00 PM"),
    ]
    slots = []
    for key, label, time in slot_map:
        recipe = recipes.get(f"{key}_id")
        if not recipe:
            continue
        slots.append({
            "key": key,
            "label": label,
            "time": time,
            "recipe": recipe,
        })
    return slots


def _calc_totals(recipes: dict):
    totals = {"calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for recipe in recipes.values():
        if not recipe:
            continue
        totals["calories"] += recipe.calories or 0
        totals["protein"] += float(recipe.protein_g or 0)
        totals["carbs"] += float(recipe.carbs_g or 0)
        totals["fat"] += float(recipe.fat_g or 0)
    return totals


def _build_grocery_list(recipes: dict, members: List):
    totals = defaultdict(lambda: {"qty": 0, "unit": ""})
    multiplier = len(members) if members else 1
    for recipe in recipes.values():
        if not recipe:
            continue
        for ing in recipe.ingredients or []:
            key = ing.get("name", "").lower()
            if not key:
                continue
            mult = multiplier if ing.get("per_person") else 1
            qty = ing.get("qty", 0) * mult
            totals[key]["qty"] += qty
            totals[key]["unit"] = ing.get("unit", "")

    return [
        {"name": name.title(), "qty": f"{value['qty']} {value['unit']}".strip()}
        for name, value in sorted(totals.items())
    ]


def _load_logo_b64():
    logo_path = os.path.join("app", "templates", "logo.png")
    if not os.path.exists(logo_path):
        return ""
    with open(logo_path, "rb") as logo_file:
        return base64.b64encode(logo_file.read()).decode()


def _load_inline_css():
    return """
    @page { size: A4; margin: 1.5cm 1.5cm; }
    body { font-family: 'Noto Sans', sans-serif; color: #1a1a1a; margin: 0; padding: 0; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
    .header img { max-height: 60px; }
    .header h1 { margin: 0; font-size: 28px; }
    .header p { margin: 4px 0 0; color: #555; }
    .macro-summary { text-align: right; font-size: 14px; color: #333; }
    .slot-card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 16px; page-break-inside: avoid; }
    .slot-card h3 { margin: 0 0 8px; font-size: 14px; color: #666; }
    .slot-card h2 { margin: 0 0 6px; font-size: 18px; }
    .slot-card p { margin: 0 0 12px; color: #444; }
    .macro-bar { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
    .macro-pill { background: #f5f5f5; border-radius: 12px; padding: 4px 10px; font-size: 11px; }
    .grocery-section { margin-top: 24px; border-top: 2px solid #ff6b35; padding-top: 16px; }
    .grocery-section h2 { margin: 0 0 12px; }
    .grocery-section table { width: 100%; border-collapse: collapse; }
    .grocery-section td { padding: 6px 8px; vertical-align: top; border-bottom: 1px solid #eee; }
    .member-note { background: #fff8e1; border-radius: 6px; padding: 10px; margin-top: 12px; }
    ol { margin: 8px 0 0 18px; padding: 0; }
    """