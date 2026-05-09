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

    # ── Meal slots ───────────────────────────────────────────────────────────
    pill_col_w = _PAGE_W / 5
    for key in ["breakfast", "morning_snack", "lunch", "evening_snack", "dinner"]:
        recipe = recipes.get(f"{key}_id")
        if not recipe:
            continue

        label, time_str = SLOT_TIMES[key]
        story.append(Paragraph(f"{label}  ·  {time_str}", sub))
        story.append(Paragraph(_esc(recipe.name), h2))
        if recipe.name_local:
            story.append(Paragraph(_esc(recipe.name_local), sub))

        # Macro pills — format Decimal values cleanly
        protein = _fmt(recipe.protein_g)
        carbs   = _fmt(recipe.carbs_g)
        fat     = _fmt(recipe.fat_g)
        prep    = f"{recipe.prep_time_mins} min" if recipe.prep_time_mins else "—"
        pill_data = [[
            f"{recipe.calories} kcal",
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
        story.append(Spacer(1, 0.2 * cm))

        if recipe.serving_unit:
            story.append(Paragraph(f"Serving: {_esc(recipe.serving_unit)}", sub))
            story.append(Spacer(1, 0.15 * cm))

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
