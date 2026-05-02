import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=0, time_limit=7200, soft_time_limit=6900)
def run_recipe_seed(self, verify: bool = True):
    """Run the full GENERATION_MATRIX as a background Celery task.
    Returns total number of recipes inserted.
    Takes 30-60 minutes and ~$15-20 in Claude API calls for 2000+ recipes.
    """
    async def _run():
        from app.config import settings
        from app.models.recipe import Recipe
        from app.services.recipe_ai_generator import generate_recipe_batch
        from scripts.seed_recipes import GENERATION_MATRIX
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        total_inserted = 0
        total_batches = len(GENERATION_MATRIX)

        async with AsyncSessionLocal() as db:
            for idx, (meal_type, cuisine, eating_mode, health_tags, count) in enumerate(GENERATION_MATRIX, 1):
                logger.info("[seed %d/%d] %s/%s/%s count=%d",
                            idx, total_batches, meal_type, cuisine, eating_mode, count)
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
                            is_verified=verify,
                            is_active=True,
                            source="ai_generated",
                        )
                        db.add(recipe)
                        valid += 1
                    except Exception as exc:
                        logger.warning("Skipping invalid recipe: %s", exc)

                await db.commit()
                total_inserted += valid
                logger.info("  inserted %d/%d. total=%d", valid, len(recipes_data), total_inserted)
                await asyncio.sleep(1)

        await engine.dispose()
        logger.info("Seed complete. Total inserted: %d", total_inserted)
        return total_inserted

    return asyncio.run(_run())
