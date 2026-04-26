"""
Seed recipe database using GPT-4o batch generation.
Run: python -m scripts.seed_recipes
"""
import asyncio
import logging
import time
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GENERATION_MATRIX = [
    # (meal_type, cuisine_region, eating_mode, health_tags, count)
    ("breakfast", "north_indian", "pure_veg", [], 10),
    ("breakfast", "south_indian", "pure_veg", [], 10),
    ("breakfast", "gujarati", "pure_veg", [], 8),
    ("breakfast", "bengali", "pure_veg", [], 8),
    ("breakfast", "north_indian", "pure_veg", ["diabetes_t2"], 8),
    ("breakfast", "north_indian", "pure_veg", ["hypertension"], 6),
    ("breakfast", "south_indian", "pure_veg", ["diabetes_t2"], 6),
    ("morning_snack", "north_indian", "pure_veg", [], 10),
    ("morning_snack", "south_indian", "pure_veg", [], 8),
    ("morning_snack", "north_indian", "pure_veg", ["diabetes_t2"], 8),
    ("lunch", "north_indian", "pure_veg", [], 15),
    ("lunch", "north_indian", "full_nv", [], 10),
    ("lunch", "south_indian", "pure_veg", [], 12),
    ("lunch", "hyderabadi", "full_nv", [], 8),
    ("lunch", "bengali", "full_nv", [], 8),
    ("lunch", "gujarati", "pure_veg", [], 8),
    ("lunch", "maharashtrian", "pure_veg", [], 8),
    ("lunch", "rajasthani", "pure_veg", [], 8),
    ("lunch", "kerala", "full_nv", [], 8),
    ("lunch", "north_indian", "pure_veg", ["diabetes_t2"], 10),
    ("lunch", "north_indian", "pure_veg", ["hypertension"], 8),
    ("lunch", "south_indian", "pure_veg", ["pcos"], 8),
    ("lunch", "north_indian", "jain", [], 8),
    ("lunch", "north_indian", "sattvic", [], 8),
    ("evening_snack", "north_indian", "pure_veg", [], 10),
    ("evening_snack", "south_indian", "pure_veg", [], 8),
    ("evening_snack", "north_indian", "pure_veg", ["diabetes_t2"], 8),
    ("dinner", "north_indian", "pure_veg", [], 12),
    ("dinner", "south_indian", "pure_veg", [], 10),
    ("dinner", "bengali", "full_nv", [], 8),
    ("dinner", "hyderabadi", "full_nv", [], 8),
    ("dinner", "gujarati", "pure_veg", [], 8),
    ("dinner", "maharashtrian", "pure_veg", [], 8),
    ("dinner", "kerala", "full_nv", [], 8),
    ("dinner", "north_indian", "pure_veg", ["diabetes_t2"], 10),
    ("dinner", "north_indian", "pure_veg", ["hypertension"], 8),
    ("dinner", "north_indian", "jain", [], 8),
    ("dinner", "north_indian", "sattvic", [], 8),
    ("dinner", "north_indian", "conditional_nv", [], 8),
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
            logger.info("[%d/%d] Generating %d recipes: %s / %s / %s", idx, total_batches, count, meal_type, cuisine, eating_mode)
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
                        is_verified=False,
                        is_active=True,
                        source="ai_generated",
                    )
                    db.add(recipe)
                    valid += 1
                except Exception as exc:
                    logger.warning("Skipping invalid recipe: %s", exc)

            await db.commit()
            total_inserted += valid
            logger.info("  → Inserted %d/%d valid recipes. Running total: %d", valid, len(recipes_data), total_inserted)

            # Rate limit: 1 request/sec
            await asyncio.sleep(1)

    logger.info("Seed complete. Total recipes inserted: %d", total_inserted)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
