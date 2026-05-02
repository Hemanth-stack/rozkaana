"""
Seed recipe database using Claude AI batch generation.
Run: python -m scripts.seed_recipes
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Target: ~2200 recipes covering all cuisines × meal types × eating modes × health tags
# All seeded recipes are auto-verified (is_verified=True) — admins can reject bad ones later
GENERATION_MATRIX = [
    # ── BREAKFAST ────────────────────────────────────────────────────────────────
    ("breakfast", "north_indian",   "pure_veg",      [],                10),
    ("breakfast", "north_indian",   "full_nv",        [],                8),
    ("breakfast", "north_indian",   "jain",           [],                8),
    ("breakfast", "north_indian",   "sattvic",        [],                8),
    ("breakfast", "north_indian",   "pure_veg",       ["diabetes_t2"],   10),
    ("breakfast", "north_indian",   "pure_veg",       ["hypertension"],  8),
    ("breakfast", "north_indian",   "pure_veg",       ["weight_loss"],   8),
    ("breakfast", "north_indian",   "pure_veg",       ["pcos"],          6),
    ("breakfast", "south_indian",   "pure_veg",       [],                10),
    ("breakfast", "south_indian",   "full_nv",        [],                6),
    ("breakfast", "south_indian",   "pure_veg",       ["diabetes_t2"],   8),
    ("breakfast", "south_indian",   "pure_veg",       ["pcos"],          6),
    ("breakfast", "gujarati",       "pure_veg",       [],                8),
    ("breakfast", "gujarati",       "jain",           [],                8),
    ("breakfast", "bengali",        "pure_veg",       [],                8),
    ("breakfast", "bengali",        "full_nv",        [],                6),
    ("breakfast", "maharashtrian",  "pure_veg",       [],                8),
    ("breakfast", "maharashtrian",  "full_nv",        [],                6),
    ("breakfast", "punjabi",        "pure_veg",       [],                8),
    ("breakfast", "punjabi",        "full_nv",        [],                6),
    ("breakfast", "hyderabadi",     "pure_veg",       [],                6),
    ("breakfast", "hyderabadi",     "full_nv",        [],                6),
    ("breakfast", "rajasthani",     "pure_veg",       [],                8),
    ("breakfast", "rajasthani",     "jain",           [],                6),
    ("breakfast", "kerala",         "pure_veg",       [],                8),
    ("breakfast", "kerala",         "full_nv",        [],                6),
    ("breakfast", "goan",           "pure_veg",       [],                6),
    ("breakfast", "goan",           "full_nv",        [],                6),
    ("breakfast", "sattvic",        "sattvic",        [],                8),

    # ── MORNING SNACK ─────────────────────────────────────────────────────────
    ("morning_snack", "north_indian",   "pure_veg",   [],                10),
    ("morning_snack", "north_indian",   "jain",       [],                6),
    ("morning_snack", "north_indian",   "pure_veg",   ["diabetes_t2"],   10),
    ("morning_snack", "north_indian",   "pure_veg",   ["weight_loss"],   8),
    ("morning_snack", "north_indian",   "pure_veg",   ["hypertension"],  6),
    ("morning_snack", "south_indian",   "pure_veg",   [],                8),
    ("morning_snack", "south_indian",   "pure_veg",   ["diabetes_t2"],   6),
    ("morning_snack", "gujarati",       "pure_veg",   [],                8),
    ("morning_snack", "gujarati",       "jain",       [],                6),
    ("morning_snack", "maharashtrian",  "pure_veg",   [],                6),
    ("morning_snack", "bengali",        "pure_veg",   [],                6),
    ("morning_snack", "punjabi",        "pure_veg",   [],                6),
    ("morning_snack", "kerala",         "pure_veg",   [],                6),
    ("morning_snack", "rajasthani",     "pure_veg",   [],                6),
    ("morning_snack", "sattvic",        "sattvic",    [],                6),

    # ── LUNCH ─────────────────────────────────────────────────────────────────
    ("lunch", "north_indian",   "pure_veg",           [],                12),
    ("lunch", "north_indian",   "full_nv",            [],                10),
    ("lunch", "north_indian",   "jain",               [],                10),
    ("lunch", "north_indian",   "sattvic",            [],                8),
    ("lunch", "north_indian",   "conditional_nv",     [],                8),
    ("lunch", "north_indian",   "pure_veg",           ["diabetes_t2"],   12),
    ("lunch", "north_indian",   "pure_veg",           ["hypertension"],  10),
    ("lunch", "north_indian",   "pure_veg",           ["weight_loss"],   10),
    ("lunch", "north_indian",   "pure_veg",           ["pcos"],          8),
    ("lunch", "north_indian",   "full_nv",            ["diabetes_t2"],   6),
    ("lunch", "south_indian",   "pure_veg",           [],                12),
    ("lunch", "south_indian",   "full_nv",            [],                10),
    ("lunch", "south_indian",   "pure_veg",           ["diabetes_t2"],   10),
    ("lunch", "south_indian",   "pure_veg",           ["pcos"],          8),
    ("lunch", "south_indian",   "pure_veg",           ["hypertension"],  6),
    ("lunch", "gujarati",       "pure_veg",           [],                10),
    ("lunch", "gujarati",       "jain",               [],                8),
    ("lunch", "gujarati",       "pure_veg",           ["diabetes_t2"],   6),
    ("lunch", "bengali",        "pure_veg",           [],                8),
    ("lunch", "bengali",        "full_nv",            [],                10),
    ("lunch", "maharashtrian",  "pure_veg",           [],                8),
    ("lunch", "maharashtrian",  "full_nv",            [],                8),
    ("lunch", "punjabi",        "pure_veg",           [],                8),
    ("lunch", "punjabi",        "full_nv",            [],                8),
    ("lunch", "hyderabadi",     "full_nv",            [],                10),
    ("lunch", "hyderabadi",     "pure_veg",           [],                6),
    ("lunch", "rajasthani",     "pure_veg",           [],                8),
    ("lunch", "rajasthani",     "jain",               [],                8),
    ("lunch", "kerala",         "full_nv",            [],                10),
    ("lunch", "kerala",         "pure_veg",           [],                8),
    ("lunch", "goan",           "full_nv",            [],                8),
    ("lunch", "goan",           "pure_veg",           [],                6),
    ("lunch", "sattvic",        "sattvic",            [],                8),

    # ── EVENING SNACK ─────────────────────────────────────────────────────────
    ("evening_snack", "north_indian",   "pure_veg",   [],                10),
    ("evening_snack", "north_indian",   "jain",       [],                6),
    ("evening_snack", "north_indian",   "pure_veg",   ["diabetes_t2"],   10),
    ("evening_snack", "north_indian",   "pure_veg",   ["weight_loss"],   8),
    ("evening_snack", "south_indian",   "pure_veg",   [],                8),
    ("evening_snack", "south_indian",   "pure_veg",   ["diabetes_t2"],   6),
    ("evening_snack", "gujarati",       "pure_veg",   [],                8),
    ("evening_snack", "gujarati",       "jain",       [],                6),
    ("evening_snack", "maharashtrian",  "pure_veg",   [],                6),
    ("evening_snack", "bengali",        "pure_veg",   [],                6),
    ("evening_snack", "punjabi",        "pure_veg",   [],                6),
    ("evening_snack", "kerala",         "pure_veg",   [],                6),
    ("evening_snack", "rajasthani",     "pure_veg",   [],                6),
    ("evening_snack", "sattvic",        "sattvic",    [],                6),

    # ── DINNER ────────────────────────────────────────────────────────────────
    ("dinner", "north_indian",   "pure_veg",          [],                12),
    ("dinner", "north_indian",   "full_nv",           [],                10),
    ("dinner", "north_indian",   "jain",              [],                10),
    ("dinner", "north_indian",   "sattvic",           [],                8),
    ("dinner", "north_indian",   "conditional_nv",    [],                8),
    ("dinner", "north_indian",   "pure_veg",          ["diabetes_t2"],   12),
    ("dinner", "north_indian",   "pure_veg",          ["hypertension"],  10),
    ("dinner", "north_indian",   "pure_veg",          ["weight_loss"],   10),
    ("dinner", "north_indian",   "pure_veg",          ["pcos"],          8),
    ("dinner", "north_indian",   "full_nv",           ["diabetes_t2"],   6),
    ("dinner", "south_indian",   "pure_veg",          [],                12),
    ("dinner", "south_indian",   "full_nv",           [],                10),
    ("dinner", "south_indian",   "pure_veg",          ["diabetes_t2"],   10),
    ("dinner", "south_indian",   "pure_veg",          ["pcos"],          8),
    ("dinner", "gujarati",       "pure_veg",          [],                10),
    ("dinner", "gujarati",       "jain",              [],                8),
    ("dinner", "bengali",        "pure_veg",          [],                8),
    ("dinner", "bengali",        "full_nv",           [],                10),
    ("dinner", "maharashtrian",  "pure_veg",          [],                10),
    ("dinner", "maharashtrian",  "full_nv",           [],                8),
    ("dinner", "punjabi",        "pure_veg",          [],                8),
    ("dinner", "punjabi",        "full_nv",           [],                10),
    ("dinner", "hyderabadi",     "full_nv",           [],                10),
    ("dinner", "hyderabadi",     "pure_veg",          [],                6),
    ("dinner", "rajasthani",     "pure_veg",          [],                8),
    ("dinner", "rajasthani",     "jain",              [],                8),
    ("dinner", "kerala",         "full_nv",           [],                10),
    ("dinner", "kerala",         "pure_veg",          [],                8),
    ("dinner", "goan",           "full_nv",           [],                10),
    ("dinner", "goan",           "pure_veg",          [],                6),
    ("dinner", "sattvic",        "sattvic",           [],                8),
]


async def main():
    from app.config import settings
    from app.models.recipe import Recipe
    from app.services.recipe_ai_generator import generate_recipe_batch

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    total_inserted = 0
    total_batches = len(GENERATION_MATRIX)

    async with AsyncSessionLocal() as db:
        for idx, (meal_type, cuisine, eating_mode, health_tags, count) in enumerate(GENERATION_MATRIX, 1):
            logger.info("[%d/%d] Generating %d recipes: %s / %s / %s %s",
                        idx, total_batches, count, meal_type, cuisine, eating_mode,
                        health_tags or "")
            try:
                recipes_data = await generate_recipe_batch(
                    meal_type=meal_type,
                    cuisine_region=cuisine,
                    eating_mode=eating_mode,
                    health_tags=health_tags,
                    count=count,
                )
            except Exception as exc:
                logger.error("Batch failed: %s", exc)
                await asyncio.sleep(5)
                continue

            valid = 0
            for data in recipes_data:
                try:
                    recipe = Recipe(
                        name=data["name"],
                        name_local=data.get("name_local"),
                        meal_type=data.get("meal_type", meal_type),
                        cuisine_region=data.get("cuisine_region", cuisine),
                        eating_mode_tags=data.get("eating_mode_tags", [eating_mode]),
                        health_safe_tags=data.get("health_safe_tags", []),
                        allergy_free_tags=data.get("allergy_free_tags", []),
                        calories=int(data.get("calories", 0)),
                        protein_g=float(data.get("protein_g", 0)),
                        carbs_g=float(data.get("carbs_g", 0)),
                        fat_g=float(data.get("fat_g", 0)),
                        fibre_g=float(data.get("fibre_g", 0)) if data.get("fibre_g") else None,
                        serving_unit=data.get("serving_unit"),
                        prep_time_mins=data.get("prep_time_mins"),
                        spice_level=data.get("spice_level", "medium"),
                        main_ingredient=data.get("main_ingredient"),
                        ingredients=data.get("ingredients", []),
                        steps=data.get("steps", []),
                        is_verified=True,   # auto-verified; admins can reject via admin panel
                        is_active=True,
                        source="ai_generated",
                    )
                    db.add(recipe)
                    valid += 1
                except Exception as exc:
                    logger.warning("Skipping invalid recipe: %s", exc)

            await db.commit()
            total_inserted += valid
            logger.info("  → Inserted %d/%d. Running total: %d", valid, len(recipes_data), total_inserted)
            await asyncio.sleep(1)

    logger.info("Seed complete. Total recipes inserted: %d", total_inserted)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
