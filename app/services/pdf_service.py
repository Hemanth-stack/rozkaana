import io
import xml.sax.saxutils as saxutils
from datetime import date
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

if TYPE_CHECKING:
    from app.models.daily_menu import DailyMenu
    from app.models.recipe import Recipe
    from app.models.user import User

# Brand colours
SAFFRON  = colors.HexColor("#E8593C")
CREAM    = colors.HexColor("#FAF7F2")
CHARCOAL = colors.HexColor("#1A1612")
GREEN    = colors.HexColor("#2E7D52")
MUTED    = colors.HexColor("#7A6E65")
BORDER   = colors.HexColor("#E8DDD0")
AMBER    = colors.HexColor("#B45309")
INDIGO   = colors.HexColor("#4338CA")

SLOT_TIMES = {
    "breakfast":     ("Breakfast",     "8:00 AM"),
    "morning_snack": ("Morning Snack", "10:30 AM"),
    "lunch":         ("Lunch",         "1:00 PM"),
    "evening_snack": ("Evening Snack", "4:30 PM"),
    "dinner":        ("Dinner",        "8:00 PM"),
}

# Usable width: A4 (595 pt) - 3 cm margins * 2 = ~510 pt = ~18 cm
_PAGE_W = A4[0] - 3 * cm   # points, used for table widths


def _esc(text: str) -> str:
    """Escape XML special characters so ReportLab's Paragraph parser doesn't choke."""
    return saxutils.escape(str(text))


def _fmt(value, decimals: int = 1) -> str:
    """Format a Decimal / float / int to a clean string without trailing zeros."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "—"
    if decimals == 0 or f == int(f):
        return str(int(f))
    return f"{f:.{decimals}f}".rstrip("0").rstrip(".")


def render_menu_pdf(
    menu: "DailyMenu",
    members: "list[User]",
    recipes: "dict[str, Recipe | None]",
    calorie_target: int = 2000,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    h1       = ParagraphStyle("h1",   fontSize=20, textColor=CHARCOAL, fontName="Helvetica-Bold", spaceAfter=4)
    h2       = ParagraphStyle("h2",   fontSize=13, textColor=CHARCOAL, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
    sub      = ParagraphStyle("sub",  fontSize=9,  textColor=MUTED,    fontName="Helvetica")
    step_sty = ParagraphStyle("step", fontSize=8.5,textColor=CHARCOAL, fontName="Helvetica", leading=13, leftIndent=10)

    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    date_str = menu.menu_date.strftime("%A, %d %B %Y")
    # Fallback chain: name → phone → email → "Member"
    member_str = ", ".join(
        m.name or getattr(m, "phone", None) or getattr(m, "email", None) or "Member"
        for m in members if m
    )
    story.append(Paragraph("Rozkaana", h1))
    story.append(Paragraph(f"Daily Meal Plan — {_esc(date_str)}", sub))
    if len(members) > 1:
        story.append(Paragraph(f"For: {_esc(member_str)}", sub))
    story.append(Spacer(1, 0.3 * cm))

    # ── Macro summary bar ────────────────────────────────────────────────────
    totals = _calc_totals(recipes)
    col_w = _PAGE_W / 4
    macro_data = [[
        _macro_cell("Calories", f"{totals['calories']} kcal", SAFFRON),
        _macro_cell("Protein",  f"{totals['protein']}g",      GREEN),
        _macro_cell("Carbs",    f"{totals['carbs']}g",        AMBER),
        _macro_cell("Fat",      f"{totals['fat']}g",          INDIGO),
    ]]
    macro_tbl = Table(macro_data, colWidths=[col_w] * 4)
    macro_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), CREAM),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(macro_tbl)
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
    story.append(Spacer(1, 0.3 * cm))

    # ── Nutrition balance warnings ────────────────────────────────────────────
    from app.services.nutrition_balance import compute_slot_serving, compute_daily_balance, SLOT_RATIOS as NB_RATIOS
    slot_map = {key: recipes.get(f"{key}_id") for key in NB_RATIOS}
    slot_servings = {
        slot: compute_slot_serving(recipe, slot, calorie_target) if recipe else {"multiplier": 1.0, "recommended_qty": "", "scaled_calories": 0}
        for slot, recipe in slot_map.items()
    }
    balance = compute_daily_balance(
        slot_map, slot_servings,
        calorie_target=calorie_target,
        protein_target_g=calorie_target * 0.12 / 4,  # rough protein min; PDF doesn't know user
        carbs_target_g=calorie_target * 0.55 / 4,
        fat_target_g=calorie_target * 0.30 / 9,
    )
    if balance["nutrition_warnings"]:
        warn_sty = ParagraphStyle("warn", fontSize=8, textColor=AMBER, fontName="Helvetica",
                                  leading=12, leftIndent=4, spaceAfter=3)
        story.append(Paragraph("Nutrition notes:", ParagraphStyle("wh", fontSize=8, textColor=AMBER,
                                fontName="Helvetica-Bold", spaceAfter=2)))
        for w in balance["nutrition_warnings"]:
            story.append(Paragraph(f"• {_esc(w)}", warn_sty))
        story.append(Spacer(1, 0.2 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 0.2 * cm))

    # ── Meal slots ───────────────────────────────────────────────────────────
    pill_col_w = _PAGE_W / 5
    for key in ["breakfast", "morning_snack", "lunch", "evening_snack", "dinner"]:
        recipe = recipes.get(f"{key}_id")
        if not recipe:
            continue

        serving_info = slot_servings.get(key, {})
        multiplier   = serving_info.get("multiplier", 1.0)
        rec_qty      = serving_info.get("recommended_qty", "")
        scaled_cal   = serving_info.get("scaled_calories", recipe.calories or 0)

        label, time_str = SLOT_TIMES[key]
        story.append(Paragraph(f"{label}  ·  {time_str}", sub))
        story.append(Paragraph(_esc(recipe.name), h2))
        if recipe.name_local:
            story.append(Paragraph(_esc(recipe.name_local), sub))

        # Serving quantity — shown prominently right after the title
        if recipe.serving_unit:
            qty_sty = ParagraphStyle(
                "qty", fontSize=9.5, textColor=GREEN, fontName="Helvetica-Bold",
                spaceBefore=2, spaceAfter=2,
            )
            story.append(Paragraph(f"1× serving: {_esc(recipe.serving_unit)}", qty_sty))

        # Recommended serving multiplier when recipe is below slot calorie target
        if rec_qty:
            rec_sty = ParagraphStyle(
                "rec", fontSize=9.5, textColor=SAFFRON, fontName="Helvetica-Bold",
                spaceBefore=1, spaceAfter=4,
            )
            story.append(Paragraph(f"Recommended: {_esc(rec_qty)}", rec_sty))

        # Per-person ingredient quantities for main components (meat/fish/dal/veg in grams)
        # Skip spices, oils, water, garnishes — only show items ≥ 30g/ml and per_person=True
        ing_lines = _format_ingredient_quantities(recipe)
        if ing_lines:
            ing_sty = ParagraphStyle(
                "ing", fontSize=8, textColor=MUTED, fontName="Helvetica",
                leading=12, leftIndent=0, spaceAfter=4,
            )
            story.append(Paragraph("  ·  ".join(ing_lines), ing_sty))

        # Macro pills — show per-recipe AND scaled if multiplier > 1
        protein = _fmt(recipe.protein_g)
        carbs   = _fmt(recipe.carbs_g)
        fat     = _fmt(recipe.fat_g)
        prep    = f"{recipe.prep_time_mins} min" if recipe.prep_time_mins else "—"
        cal_label = (
            f"{recipe.calories} kcal → {scaled_cal} kcal (×{multiplier})"
            if multiplier > 1.05 else f"{recipe.calories} kcal"
        )
        pill_data = [[
            cal_label,
            f"P: {protein}g",
            f"C: {carbs}g",
            f"F: {fat}g",
            f"Prep: {prep}",
        ]]
        pill_tbl = Table(pill_data, colWidths=[pill_col_w] * 5)
        pill_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), CREAM),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TEXTCOLOR",     (0, 0), (0, 0),   SAFFRON),
        ]))
        story.append(pill_tbl)
        story.append(Spacer(1, 0.25 * cm))

        # Cooking steps
        for i, step in enumerate(recipe.steps or [], 1):
            story.append(Paragraph(f"{i}. {_esc(step)}", step_sty))

        story.append(Spacer(1, 0.4 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 0.3 * cm))

    # ── Grocery list (household only) ────────────────────────────────────────
    if len(members) > 1:
        story.append(Paragraph("Grocery List", h1))
        story.append(Paragraph(f"For {len(members)} members", sub))
        story.append(Spacer(1, 0.3 * cm))
        grocery = _build_grocery_list(recipes, len(members))
        if grocery:
            g_data = [["Ingredient", "Quantity"]] + [
                [_esc(g["name"]), f"{g['qty']} {g['unit']}"] for g in grocery
            ]
            g_tbl = Table(g_data, colWidths=[_PAGE_W * 0.68, _PAGE_W * 0.32])
            g_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0),  CHARCOAL),
                ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
                ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, CREAM]),
                ("GRID",          (0, 0), (-1, -1), 0.5, BORDER),
                ("ALIGN",         (1, 0), (1, -1),  "CENTER"),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(g_tbl)

    doc.build(story)
    return buf.getvalue()


# Keywords that identify a roti/flatbread — displayed as count, not grams
_ROTI_KEYWORDS = {
    "roti", "chapathi", "chapati", "phulka", "paratha", "parotta", "naan",
    "puri", "luchi", "thepla", "jolada rotti", "akki roti", "bajra roti",
    "jowar roti", "ragi roti", "makki roti",
}

# Keywords that identify a starch base — displayed in grams
_RICE_KEYWORDS = {
    "rice", "sadam", "annam", "chawal", "matta rice", "red rice",
    "brown rice", "foxtail millet rice", "barnyard millet rice", "idli",
    "dosa", "pesarattu", "upma", "pongal", "puttu", "idiyappam",
    "appam", "uttapam", "adai", "akki roti",
}


def _format_ingredient_quantities(recipe: "Recipe") -> list[str]:
    """Return concise quantity strings for main per-person ingredients.

    Shows: roti/flatbread as count, rice/dal/meat/veg in grams.
    Skips: spices, oils, salt, water, and tiny quantities (<30g/ml).
    """
    ingredients = recipe.ingredients
    if not ingredients or not isinstance(ingredients, list):
        return []

    # Names that indicate a condiment/spice/oil — skip these
    _SKIP_KEYWORDS = {
        "oil", "salt", "water", "spice", "chilli powder", "turmeric",
        "cumin", "mustard", "pepper", "garam masala", "coriander powder",
        "fenugreek", "asafoetida", "hing", "ghee", "butter", "sugar",
        "jaggery", "tamarind", "curry leaves", "bay leaf",
    }

    lines: list[str] = []
    for ing in ingredients:
        if not isinstance(ing, dict):
            continue
        name_raw = (ing.get("name") or "").strip()
        name     = name_raw.lower()
        qty      = ing.get("qty")
        unit     = (ing.get("unit") or "").strip().lower()
        per_person = ing.get("per_person", False)

        if not name_raw or qty is None:
            continue
        if not per_person:
            continue  # skip shared/bulk ingredients

        # Skip spice/condiment/tiny items
        if any(kw in name for kw in _SKIP_KEYWORDS):
            continue

        try:
            qty_f = float(qty)
        except (TypeError, ValueError):
            continue

        is_roti = any(kw in name for kw in _ROTI_KEYWORDS)
        is_countable = any(kw in name for kw in {"idli", "idly", "vada", "vadai", "dosa",
                                                   "pesarattu", "vadalu", "egg", "eggs"})

        if is_roti:
            count = int(round(qty_f))
            label = name_raw.split("(")[0].split(",")[0].strip()
            lines.append(f"{count} {label}")
        elif is_countable and unit in ("nos", "no", "piece", "pieces", ""):
            count = int(round(qty_f))
            lines.append(f"{count} {name_raw.split('(')[0].split(',')[0].strip()}")
        elif unit in ("g", "grams", "gram") and qty_f >= 30:
            # Use ingredient name up to the first comma or parenthesis — whichever comes first
            display = name_raw.split(",")[0].split("(")[0].strip().title()
            lines.append(f"{display} {int(round(qty_f))}g")
        elif unit in ("ml", "milliliters", "millilitres") and qty_f >= 30:
            display = name_raw.split(",")[0].split("(")[0].strip().title()
            lines.append(f"{display} {int(round(qty_f))}ml")

        if len(lines) >= 5:
            break

    return lines


def _macro_cell(label: str, value: str, colour: colors.Color) -> list:
    """Return a [value_paragraph, label_paragraph] list for use in a Table cell."""
    val_sty = ParagraphStyle("mv", fontSize=11, textColor=colour,  fontName="Helvetica-Bold", alignment=1)
    lbl_sty = ParagraphStyle("ml", fontSize=7.5, textColor=MUTED, fontName="Helvetica",       alignment=1)
    return [Paragraph(value, val_sty), Paragraph(label, lbl_sty)]


def _calc_totals(recipes: dict) -> dict:
    return {
        "calories": sum(r.calories or 0 for r in recipes.values() if r),
        "protein":  _fmt(sum(float(r.protein_g or 0) for r in recipes.values() if r)),
        "carbs":    _fmt(sum(float(r.carbs_g   or 0) for r in recipes.values() if r)),
        "fat":      _fmt(sum(float(r.fat_g     or 0) for r in recipes.values() if r)),
    }


def _build_grocery_list(recipes: dict, member_count: int) -> list[dict]:
    from app.services.grocery_service import build_grocery_list
    return build_grocery_list(recipes, member_count)
