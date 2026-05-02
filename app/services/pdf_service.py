import io
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

if TYPE_CHECKING:
    from app.models.daily_menu import DailyMenu
    from app.models.recipe import Recipe
    from app.models.user import User

# Brand colours
SAFFRON = colors.HexColor("#E8593C")
CREAM   = colors.HexColor("#FAF7F2")
CHARCOAL= colors.HexColor("#1A1612")
GREEN   = colors.HexColor("#2E7D52")
MUTED   = colors.HexColor("#7A6E65")
BORDER  = colors.HexColor("#E8DDD0")

SLOT_TIMES = {
    "breakfast":     ("Breakfast",     "8:00 AM"),
    "morning_snack": ("Morning Snack", "10:30 AM"),
    "lunch":         ("Lunch",         "1:00 PM"),
    "evening_snack": ("Evening Snack", "4:30 PM"),
    "dinner":        ("Dinner",        "8:00 PM"),
}


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

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", fontSize=20, textColor=CHARCOAL, fontName="Helvetica-Bold", spaceAfter=4)
    h2 = ParagraphStyle("h2", fontSize=13, textColor=CHARCOAL, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
    sub = ParagraphStyle("sub", fontSize=9, textColor=MUTED, fontName="Helvetica")
    body = ParagraphStyle("body", fontSize=9, textColor=CHARCOAL, fontName="Helvetica", leading=14)
    step_style = ParagraphStyle("step", fontSize=8.5, textColor=CHARCOAL, fontName="Helvetica", leading=13, leftIndent=10)

    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    date_str = menu.menu_date.strftime("%A, %d %B %Y")
    member_str = ", ".join(m.name or m.phone for m in members if m)
    story.append(Paragraph("🍱 Rozkaana", h1))
    story.append(Paragraph(f"Daily Meal Plan — {date_str}", sub))
    if len(members) > 1:
        story.append(Paragraph(f"For: {member_str}", sub))
    story.append(Spacer(1, 0.3 * cm))

    # Macro summary bar
    totals = _calc_totals(recipes)
    macro_data = [[
        _macro_cell("Calories", f"{totals['calories']} kcal", SAFFRON),
        _macro_cell("Protein",  f"{totals['protein']}g",     GREEN),
        _macro_cell("Carbs",    f"{totals['carbs']}g",       colors.HexColor("#B45309")),
        _macro_cell("Fat",      f"{totals['fat']}g",         colors.HexColor("#4338CA")),
    ]]
    macro_tbl = Table(macro_data, colWidths=[4.4 * cm] * 4)
    macro_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CREAM),
        ("ROUNDEDCORNERS", [8]),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(macro_tbl)
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
    story.append(Spacer(1, 0.3 * cm))

    # ── Meal slots ───────────────────────────────────────────────────────────
    slot_keys = ["breakfast", "morning_snack", "lunch", "evening_snack", "dinner"]
    for key in slot_keys:
        recipe = recipes.get(f"{key}_id")
        if not recipe:
            continue

        label, time_str = SLOT_TIMES[key]
        story.append(Paragraph(f"{label}  ·  {time_str}", sub))
        story.append(Paragraph(recipe.name, h2))
        if recipe.name_local:
            story.append(Paragraph(recipe.name_local, sub))

        # Macro pills
        pill_data = [[
            f"{recipe.calories} kcal",
            f"P: {recipe.protein_g}g",
            f"C: {recipe.carbs_g}g",
            f"F: {recipe.fat_g}g",
            f"Prep: {recipe.prep_time_mins or '—'} min",
        ]]
        pill_tbl = Table(pill_data, colWidths=[3.2 * cm] * 5)
        pill_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CREAM),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TEXTCOLOR", (0, 0), (0, 0), SAFFRON),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ]))
        story.append(pill_tbl)
        story.append(Spacer(1, 0.2 * cm))

        story.append(Paragraph(f"Serving: {recipe.serving_unit or '1 portion'}", sub))
        story.append(Spacer(1, 0.15 * cm))

        # Steps
        if recipe.steps:
            for i, step in enumerate(recipe.steps, 1):
                story.append(Paragraph(f"{i}. {step}", step_style))
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
            g_data = [["Ingredient", "Quantity"]] + [[g["name"], f"{g['qty']} {g['unit']}"] for g in grocery]
            g_tbl = Table(g_data, colWidths=[11 * cm, 5 * cm])
            g_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), CHARCOAL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CREAM]),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(g_tbl)

    doc.build(story)
    return buf.getvalue()


def _macro_cell(label: str, value: str, colour) -> Paragraph:
    styles = getSampleStyleSheet()
    val_style = ParagraphStyle("mv", fontSize=11, textColor=colour, fontName="Helvetica-Bold", alignment=1)
    lbl_style = ParagraphStyle("ml", fontSize=7.5, textColor=MUTED, fontName="Helvetica", alignment=1)
    return [Paragraph(value, val_style), Paragraph(label, lbl_style)]


def _calc_totals(recipes: dict) -> dict:
    return {
        "calories": sum(r.calories or 0 for r in recipes.values() if r),
        "protein":  round(sum(float(r.protein_g or 0) for r in recipes.values() if r), 1),
        "carbs":    round(sum(float(r.carbs_g or 0) for r in recipes.values() if r), 1),
        "fat":      round(sum(float(r.fat_g or 0) for r in recipes.values() if r), 1),
        "fibre":    round(sum(float(r.fibre_g or 0) for r in recipes.values() if r), 1),
    }


def _build_grocery_list(recipes: dict, member_count: int) -> list[dict]:
    from app.services.grocery_service import build_grocery_list
    return build_grocery_list(recipes, member_count)
