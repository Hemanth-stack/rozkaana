"""
Reads dataset/IndianFoodDatasetCSV.csv, applies taxonomy mapping and filtering,
writes dataset/clean_recipes.csv.

Run: PYTHONPATH=. python -m scripts.clean_csv
"""

import csv
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INPUT_CSV = BASE / "dataset" / "IndianFoodDatasetCSV.csv"
OUTPUT_CSV = BASE / "dataset" / "clean_recipes.csv"

# ---------------------------------------------------------------------------
# Taxonomy maps
# ---------------------------------------------------------------------------

CUISINE_MAP: dict[str, str] = {
    "Indian": "north_indian",
    "North Indian Recipes": "north_indian",
    "Rajasthani": "rajasthani",
    "Bengali Recipes": "bengali",
    "Gujarati Recipes": "gujarati",
    "Gujarati Recipes﻿": "gujarati",   # BOM artifact
    "Maharashtrian Recipes": "maharashtrian",
    "Kerala Recipes": "kerala",
    "Goan Recipes": "goan",
    "Punjabi": "punjabi",
    "Hyderabadi": "hyderabadi",
    "South Indian Recipes": "south_indian",
    "Tamil Nadu": "south_indian",
    "Karnataka": "south_indian",
    "Andhra": "south_indian",
    "Chettinad": "south_indian",
    "Mangalorean": "south_indian",
    "Udupi": "south_indian",
    "Kongunadu": "south_indian",
    "Coastal Karnataka": "south_indian",
    "South Karnataka": "south_indian",
    "North Karnataka": "south_indian",
    "Malabar": "kerala",
    "Kashmiri": "north_indian",
    "Awadhi": "north_indian",
    "Mughlai": "north_indian",
    "Lucknowi": "north_indian",
    "Uttar Pradesh": "north_indian",
    "Uttarakhand-North Kumaon": "north_indian",
    "Haryana": "north_indian",
    "Himachal": "north_indian",
    "Bihari": "north_indian",
    "Jharkhand": "north_indian",
    "Sindhi": "north_indian",
    "Nagaland": "north_indian",
    "North East India Recipes": "north_indian",
    "Oriya Recipes": "bengali",
    "Assamese": "bengali",
    "Parsi Recipes": "maharashtrian",
    "Konkan": "maharashtrian",
    "No Onion No Garlic (Sattvic)": "sattvic",
}

COURSE_MAP: dict[str, str] = {
    "Main Course": "lunch",
    "Lunch": "lunch",
    "One Pot Dish": "lunch",
    "Dinner": "dinner",
    "Breakfast": "breakfast",
    "Indian Breakfast": "breakfast",
    "South Indian Breakfast": "breakfast",
    "North Indian Breakfast": "breakfast",
    "World Breakfast": "breakfast",
    "Brunch": "breakfast",
    "Snack": "evening_snack",
    "Dessert": "evening_snack",
    "Appetizer": "morning_snack",
}

DIET_MAP: dict[str, list[str]] = {
    "Vegetarian": ["pure_veg"],
    "Non Vegeterian": ["full_nv", "conditional_nv"],   # CSV typo preserved
    "Non Vegetarian": ["full_nv", "conditional_nv"],
    "Vegan": ["pure_veg", "jain"],
    "Eggetarian": ["conditional_nv"],
    "Diabetic Friendly": ["pure_veg"],
    "High Protein Vegetarian": ["pure_veg"],
    "High Protein Non Vegetarian": ["full_nv", "conditional_nv"],
    "No Onion No Garlic (Sattvic)": ["sattvic", "jain", "pure_veg"],
    "Gluten Free": ["pure_veg"],
    "Sugar Free Diet": ["pure_veg"],
}

# Regex: leading quantity + common units
_LEADING_QTY = re.compile(
    r"^[\d½¼¾\s/.\-]+\s*"
    r"(?:cups?|tbsps?|tsps?|teaspoons?|tablespoons?|g|kg|ml|l|"
    r"pieces?|pinch|handful|bunch|large|small|medium|inch|cm|nos?\.?|"
    r"to\s+taste|as\s+required|as\s+needed)\s*",
    re.IGNORECASE,
)

# Devanagari Unicode block
_HINDI_RE = re.compile(r"[ऀ-ॿ]")


def has_hindi(text: str) -> bool:
    return bool(_HINDI_RE.search(text))


def parse_single_ingredient(item: str) -> dict:
    raw = item.strip()
    name = _LEADING_QTY.sub("", raw).strip()
    # Strip trailing descriptors like " - deseeded", " - chopped"
    name = re.split(r"\s+-\s+", name)[0].strip()
    # Strip parenthetical translations in brackets
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    name = name.strip(" ,.")
    return {"name": name.lower(), "qty": None, "unit": None, "raw": raw}


def parse_ingredients(raw: str) -> list[dict]:
    if not raw or has_hindi(raw):
        return []
    items = [i.strip() for i in raw.split(",") if i.strip()]
    result = []
    for item in items[:30]:
        parsed = parse_single_ingredient(item)
        if parsed["name"]:
            result.append(parsed)
    return result


def _safe_int(val: str) -> int | None:
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def clean_row(row: dict) -> dict | None:
    cuisine_raw = row.get("Cuisine", "").strip()
    course_raw = row.get("Course", "").strip()
    diet_raw = row.get("Diet", "").strip()
    ingredients_raw = row.get("Ingredients", "").strip()

    cuisine_region = CUISINE_MAP.get(cuisine_raw)
    meal_type = COURSE_MAP.get(course_raw)
    eating_mode_tags = DIET_MAP.get(diet_raw)

    if not cuisine_region or not meal_type or not eating_mode_tags:
        return None

    if has_hindi(ingredients_raw):
        return None

    ingredients_jsonb = parse_ingredients(ingredients_raw)

    name = row.get("TranslatedRecipeName", "").strip() or row.get("RecipeName", "").strip()
    name_raw = row.get("RecipeName", "").strip()
    name_local = name_raw if name_raw and name_raw != name else None

    instructions_raw = row.get("TranslatedInstructions", "").strip() or row.get("Instructions", "").strip()

    return {
        "name": name,
        "name_local": name_local,
        "meal_type": meal_type,
        "cuisine_region": cuisine_region,
        "eating_mode_tags": json.dumps(eating_mode_tags),
        "ingredients_jsonb": json.dumps(ingredients_jsonb),
        "prep_time_mins": _safe_int(row.get("PrepTimeInMins", "")),
        "total_time_mins": _safe_int(row.get("TotalTimeInMins", "")),
        "servings": _safe_int(row.get("Servings", "")) or 4,
        "instructions_raw": instructions_raw,
        "source_url": row.get("URL", "").strip(),
    }


def main() -> None:
    stats = {
        "total": 0,
        "valid": 0,
        "skipped_hindi": 0,
        "skipped_cuisine": 0,
        "skipped_course": 0,
        "skipped_diet": 0,
        "dupes_removed": 0,
    }

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    with open(INPUT_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["total"] += 1

            cuisine_raw = row.get("Cuisine", "").strip()
            course_raw = row.get("Course", "").strip()
            diet_raw = row.get("Diet", "").strip()
            ingredients_raw = row.get("Ingredients", "").strip()

            if has_hindi(ingredients_raw):
                stats["skipped_hindi"] += 1
                continue
            if cuisine_raw not in CUISINE_MAP:
                stats["skipped_cuisine"] += 1
                continue
            if course_raw not in COURSE_MAP:
                stats["skipped_course"] += 1
                continue
            if diet_raw not in DIET_MAP:
                stats["skipped_diet"] += 1
                continue

            cleaned = clean_row(row)
            if not cleaned:
                continue

            key = (cleaned["meal_type"], cleaned["name"].lower())
            if key in seen:
                stats["dupes_removed"] += 1
                continue
            seen.add(key)

            rows.append(cleaned)
            stats["valid"] += 1

    fieldnames = [
        "name", "name_local", "meal_type", "cuisine_region",
        "eating_mode_tags", "ingredients_jsonb",
        "prep_time_mins", "total_time_mins", "servings",
        "instructions_raw", "source_url",
    ]

    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. Total rows: {stats['total']}")
    print(f"  Valid          : {stats['valid']}")
    print(f"  Skipped hindi  : {stats['skipped_hindi']}")
    print(f"  Skipped cuisine: {stats['skipped_cuisine']}")
    print(f"  Skipped course : {stats['skipped_course']}")
    print(f"  Skipped diet   : {stats['skipped_diet']}")
    print(f"  Dupes removed  : {stats['dupes_removed']}")
    print(f"Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
