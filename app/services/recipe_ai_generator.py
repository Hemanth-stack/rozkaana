import json
import re
import openai
from app.config import settings

SYSTEM_PROMPT = """You are a certified Indian nutritionist and chef.
Generate authentic Indian recipes in strict JSON format.
All macros must be accurate per the IFCT (Indian Food Composition Tables).
Never invent macros. Use real Indian ingredient quantities.
Output ONLY valid JSON — no markdown, no commentary."""

USER_PROMPT_TEMPLATE = """Generate {count} unique Indian recipes for:
- Meal type: {meal_type}
- Cuisine region: {cuisine_region}
- Dietary mode: {eating_mode}
- Health condition safe for: {health_tags}
- Spice level: {spice_level}

Return a JSON array. Each recipe must have:
{{
  "name": "Recipe Name",
  "name_local": "Local language name if applicable",
  "meal_type": "{meal_type}",
  "cuisine_region": "{cuisine_region}",
  "eating_mode_tags": ["pure_veg"],
  "health_safe_tags": ["diabetes_t2", "hypertension"],
  "allergy_free_tags": ["gluten_free"],
  "calories": 320,
  "protein_g": 18.5,
  "carbs_g": 42.0,
  "fat_g": 8.2,
  "fibre_g": 6.1,
  "serving_unit": "1 bowl (250ml)",
  "prep_time_mins": 25,
  "spice_level": "medium",
  "main_ingredient": "dal",
  "ingredients": [
    {{"name": "masoor dal", "qty": 80, "unit": "g", "per_person": true}},
    {{"name": "onion", "qty": 50, "unit": "g", "per_person": false}}
  ],
  "steps": [
    "Wash and soak dal for 30 minutes.",
    "Heat oil in a pressure cooker..."
  ]
}}"""

openai.api_key = settings.openai_api_key


def _find_json(text: str):
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        try:
            obj, end = decoder.raw_decode(text[idx:])
            return obj
        except json.JSONDecodeError:
            idx += 1
    raise ValueError("No valid JSON found in model response")


def _validate_recipe(recipe: dict) -> bool:
    required_keys = [
        "name", "name_local", "meal_type", "cuisine_region",
        "eating_mode_tags", "health_safe_tags", "allergy_free_tags",
        "calories", "protein_g", "carbs_g", "fat_g", "fibre_g",
        "serving_unit", "prep_time_mins", "spice_level",
        "main_ingredient", "ingredients", "steps"
    ]
    for key in required_keys:
        if key not in recipe:
            return False
    if not isinstance(recipe.get("ingredients"), list):
        return False
    if not isinstance(recipe.get("steps"), list):
        return False
    return True


async def generate_recipe_batch(
    meal_type,
    cuisine_region,
    eating_mode,
    health_tags=None,
    count=5,
    spice_level="medium"
):
    health_tags = health_tags or []
    content = USER_PROMPT_TEMPLATE.format(
        count=count,
        meal_type=meal_type,
        cuisine_region=cuisine_region,
        eating_mode=eating_mode,
        health_tags=", ".join(health_tags) or "general healthy",
        spice_level=spice_level,
    )
    response = await openai.ChatCompletion.acreate(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        temperature=0.7,
        max_tokens=1200,
    )
    raw = response.choices[0].message["content"]
    payload = _find_json(raw)
    if isinstance(payload, list):
        recipes = payload
    elif isinstance(payload, dict):
        recipes = payload.get("recipes") or payload.get("data") or []
    else:
        recipes = []

    valid_recipes = []
    for recipe in recipes:
        if not isinstance(recipe, dict):
            continue
        if _validate_recipe(recipe):
            valid_recipes.append(recipe)
    return valid_recipes