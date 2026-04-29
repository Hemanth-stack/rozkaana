import json
import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)

SYSTEM_PROMPT = """You are a certified Indian nutritionist and chef.
Generate authentic Indian recipes in strict JSON format.
All macros must be accurate per the IFCT (Indian Food Composition Tables).
Never invent macros. Use real Indian ingredient quantities.
Output ONLY valid JSON — no markdown, no commentary, no code fences."""

USER_PROMPT_TEMPLATE = """Generate {count} unique Indian recipes for:
- Meal type: {meal_type}
- Cuisine region: {cuisine_region}
- Dietary mode: {eating_mode}
- Health condition safe for: {health_tags}

Return a JSON object with key "recipes" containing an array. Each recipe must have:
{{
  "name": "Recipe Name",
  "name_local": "Local language name if applicable",
  "meal_type": "{meal_type}",
  "cuisine_region": "{cuisine_region}",
  "eating_mode_tags": ["{eating_mode}"],
  "health_safe_tags": ["general_healthy"],
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
    "Heat oil in a pressure cooker and add cumin seeds.",
    "Add onions and saute until golden.",
    "Add spices and cook 2 minutes.",
    "Add dal and 2 cups water, pressure cook 3 whistles.",
    "Adjust seasoning and serve hot."
  ]
}}"""


def _validate_recipe(recipe: dict) -> bool:
    required = [
        "name", "meal_type", "cuisine_region", "eating_mode_tags",
        "calories", "protein_g", "carbs_g", "fat_g",
        "ingredients", "steps",
    ]
    for key in required:
        if key not in recipe:
            return False
    if not isinstance(recipe.get("ingredients"), list) or len(recipe["ingredients"]) < 2:
        return False
    if not isinstance(recipe.get("steps"), list) or len(recipe["steps"]) < 3:
        return False
    if not (recipe.get("calories", 0) > 0):
        return False
    return True


async def _call_claude_raw(model: str, prompt: str) -> str:
    response = _client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "max_tokens":
        logger.warning("Claude hit max_tokens — response may be truncated")
    return response.content[0].text


async def _call_claude(model: str, prompt: str) -> list[dict]:
    try:
        raw = await _call_claude_raw(model, prompt)
        payload = json.loads(raw)
        if isinstance(payload, list):
            return payload
        elif isinstance(payload, dict):
            recipes = payload.get("recipes") or []
            if not isinstance(recipes, list):
                for v in payload.values():
                    if isinstance(v, list):
                        return v
            return recipes
        return []
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error in sub-batch: %s", exc)
        return []
    except Exception as exc:
        logger.error("Claude sub-batch call failed: %s", exc)
        return []


async def generate_recipe_batch(
    meal_type: str,
    cuisine_region: str,
    eating_mode: str,
    health_tags: list[str] | None = None,
    count: int = 5,
    model: str = "claude-sonnet-4-6",
) -> list[dict]:
    health_tags = health_tags or []
    prompt = USER_PROMPT_TEMPLATE.format(
        count=count,
        meal_type=meal_type,
        cuisine_region=cuisine_region,
        eating_mode=eating_mode,
        health_tags=", ".join(health_tags) or "general healthy",
    )

    # If count > 5 split into sub-batches of 5 to avoid token limit truncation
    if count > 5:
        all_valid: list[dict] = []
        batch_size = 5
        for i in range(0, count, batch_size):
            batch_count = min(batch_size, count - i)
            batch = await _call_claude(
                model=model,
                prompt=USER_PROMPT_TEMPLATE.format(
                    count=batch_count,
                    meal_type=meal_type,
                    cuisine_region=cuisine_region,
                    eating_mode=eating_mode,
                    health_tags=", ".join(health_tags) or "general healthy",
                ),
            )
            all_valid.extend([r for r in batch if isinstance(r, dict) and _validate_recipe(r)])
        logger.info("Generated %d valid recipes (batched) for %s/%s/%s", len(all_valid), meal_type, cuisine_region, eating_mode)
        return all_valid

    recipes = await _call_claude(model, prompt)
    valid = [r for r in recipes if isinstance(r, dict) and _validate_recipe(r)]
    logger.info(
        "Generated %d/%d valid recipes for %s/%s/%s",
        len(valid), len(recipes), meal_type, cuisine_region, eating_mode,
    )
    return valid
