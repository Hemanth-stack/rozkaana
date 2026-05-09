import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=0, time_limit=14400, soft_time_limit=13800)
def run_recipe_seed(self, verify: bool = True):
    """
    Generate recipes for every entry in GENERATION_MATRIX.

    Deduplication happens at two levels:
    1. PROMPT-LEVEL: existing recipe names for each (meal_type, cuisine) combination
       are injected into the Claude prompt so it generates novel dishes upfront.
       This eliminates wasted input tokens on recipes Claude would create that we'd
       then throw away.
    2. POST-GENERATION: any remaining name collisions (across eating_mode variants of
       the same cuisine) are caught and skipped before DB insert.

    Returns {inserted, skipped}.
    Estimated: ~90 min, ~$35-45 in Claude API calls for 5800 recipes.
    """
    async def _run():
        from app.config import settings
        from app.data.seed_matrix import GENERATION_MATRIX, TOTAL_TARGET
        from app.models.recipe import Recipe
        from app.services.recipe_ai_generator import generate_recipe_batch
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import func, select as sa_select

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        total_inserted = 0
        total_skipped = 0
        total_batches = len(GENERATION_MATRIX)

        logger.info("Starting recipe seed: %d matrix entries, target ~%d recipes",
                    total_batches, TOTAL_TARGET)

        async with AsyncSessionLocal() as db:
            # Build a flat dedup set (meal_type, lower_name) for post-generation guard
            existing_result = await db.execute(
                sa_select(Recipe.meal_type, func.lower(Recipe.name))
                .where(Recipe.is_active == True)  # noqa
            )
            dedup_set: set[tuple] = set(existing_result.fetchall())

            # Build a lookup {(meal_type, cuisine_region): [name, ...]} for prompt injection.
            # We group by (meal_type, cuisine) rather than full combination because recipes
            # from different eating_mode variants of the same cuisine overlap significantly.
            names_result = await db.execute(
                sa_select(Recipe.meal_type, Recipe.cuisine_region, Recipe.name)
                .where(Recipe.is_active == True)  # noqa
            )
            names_by_slot: dict[tuple, list[str]] = {}
            for meal_t, cuisine_r, name in names_result.fetchall():
                key = (meal_t, cuisine_r)
                names_by_slot.setdefault(key, []).append(name)

            logger.info("Loaded %d existing recipes for prompt deduplication context",
                        len(dedup_set))

            for idx, (meal_type, cuisine, eating_mode, health_tags, count) in enumerate(GENERATION_MATRIX, 1):
                # Names already in DB for this meal_type + cuisine (prompt context)
                prompt_existing = names_by_slot.get((meal_type, cuisine), [])

                logger.info("[%d/%d] %s/%s/%s %s  need=%d  prompt_context=%d existing",
                            idx, total_batches, meal_type, cuisine, eating_mode,
                            health_tags or "", count, len(prompt_existing))
                try:
                    recipes_data = await generate_recipe_batch(
                        meal_type=meal_type,
                        cuisine_region=cuisine,
                        eating_mode=eating_mode,
                        health_tags=health_tags,
                        count=count,
                        existing_names=prompt_existing,   # injected into prompt
                    )
                except Exception as exc:
                    logger.error("Batch failed [%d/%d]: %s", idx, total_batches, exc)
                    await asyncio.sleep(5)
                    continue

                batch_inserted = 0
                for data in recipes_data:
                    name_lower = (data.get("name") or "").strip().lower()
                    if not name_lower:
                        continue

                    # Post-generation dedup guard (catches any prompt misses)
                    key = (meal_type, name_lower)
                    if key in dedup_set:
                        total_skipped += 1
                        continue
                    dedup_set.add(key)

                    # Also update the prompt context for subsequent batches in this run
                    names_by_slot.setdefault((meal_type, cuisine), []).append(data["name"])

                    try:
                        raw_safe_tags = data.get("health_safe_tags") or []
                        merged_safe_tags = list(set(raw_safe_tags + (health_tags or []) + ["general_healthy"]))
                        def _s(val, maxlen):
                            return str(val)[:maxlen] if val else None
                        recipe = Recipe(
                            name=data["name"][:200],
                            name_local=_s(data.get("name_local"), 200),
                            meal_type=meal_type,
                            cuisine_region=data.get("cuisine_region", cuisine)[:30],
                            eating_mode_tags=data.get("eating_mode_tags", [eating_mode]),
                            health_safe_tags=merged_safe_tags,
                            allergy_free_tags=data.get("allergy_free_tags", []),
                            calories=int(data.get("calories", 0)),
                            protein_g=float(data.get("protein_g", 0)),
                            carbs_g=float(data.get("carbs_g", 0)),
                            fat_g=float(data.get("fat_g", 0)),
                            fibre_g=float(data.get("fibre_g", 0)) if data.get("fibre_g") else None,
                            sugar_g=float(data.get("sugar_g", 0)) if data.get("sugar_g") else None,
                            sodium_mg=float(data.get("sodium_mg", 0)) if data.get("sodium_mg") else None,
                            potassium_mg=float(data.get("potassium_mg", 0)) if data.get("potassium_mg") else None,
                            iron_mg=float(data.get("iron_mg", 0)) if data.get("iron_mg") else None,
                            calcium_mg=float(data.get("calcium_mg", 0)) if data.get("calcium_mg") else None,
                            vitamin_c_mg=float(data.get("vitamin_c_mg", 0)) if data.get("vitamin_c_mg") else None,
                            vitamin_b12_mcg=float(data.get("vitamin_b12_mcg", 0)) if data.get("vitamin_b12_mcg") else None,
                            vitamin_d_mcg=float(data.get("vitamin_d_mcg", 0)) if data.get("vitamin_d_mcg") else None,
                            glycemic_index=int(data.get("glycemic_index", 0)) if data.get("glycemic_index") else None,
                            serving_unit=_s(data.get("serving_unit"), 200),
                            prep_time_mins=data.get("prep_time_mins"),
                            spice_level=_s(data.get("spice_level", "medium"), 20),
                            main_ingredient=_s(data.get("main_ingredient"), 100),
                            ingredients=data.get("ingredients", []),
                            steps=data.get("steps", []),
                            is_verified=verify,
                            is_active=True,
                            source="ai_generated",
                        )
                        db.add(recipe)
                        batch_inserted += 1
                    except Exception as exc:
                        logger.warning("Skipping invalid recipe '%s': %s", data.get("name"), exc)

                await db.commit()
                total_inserted += batch_inserted
                logger.info("  +%d inserted  %d post-gen skipped  total=%d",
                            batch_inserted, total_skipped, total_inserted)
                await asyncio.sleep(1)

        await engine.dispose()
        logger.info("Seed complete. Inserted: %d  Skipped duplicates: %d",
                    total_inserted, total_skipped)
        return {"inserted": total_inserted, "skipped": total_skipped}

    return asyncio.run(_run())
