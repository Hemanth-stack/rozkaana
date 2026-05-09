"""
Seed recipe database using Claude AI batch generation.
Run from project root: PYTHONPATH=. python -m scripts.seed_recipes

Imports the shared GENERATION_MATRIX from app/data/seed_matrix.py.

Resume behaviour: for each matrix entry, counts existing DB recipes that
match (meal_type, cuisine, eating_mode, health_tags). If already at or
above target, the entry is skipped entirely (no Claude call). If partially
filled, only the shortfall is requested.
"""
import asyncio
import logging
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def _count_existing(db: AsyncSession, Recipe, meal_type, cuisine, eating_mode, health_tags) -> int:
    """Count active recipes in DB that satisfy this matrix entry's filters."""
    filters = [
        Recipe.meal_type == meal_type,
        Recipe.cuisine_region == cuisine,
        Recipe.eating_mode_tags.op("@>")(cast([eating_mode], PG_ARRAY(String))),
        Recipe.is_active == True,  # noqa
    ]
    for tag in (health_tags or []):
        filters.append(Recipe.health_safe_tags.op("@>")(cast([tag], PG_ARRAY(String))))
    result = await db.execute(select(func.count()).where(*filters))
    return result.scalar() or 0


async def main():
    from app.config import settings
    from app.data.seed_matrix import GENERATION_MATRIX, TOTAL_TARGET
    from app.models.recipe import Recipe
    from app.services.recipe_ai_generator import generate_recipe_batch

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    total_inserted = 0
    total_skipped_dup = 0
    total_batches_skipped = 0
    total_batches = len(GENERATION_MATRIX)

    logger.info("Starting seed: %d matrix entries, target ~%d recipes", total_batches, TOTAL_TARGET)

    async with AsyncSessionLocal() as db:
        # Flat dedup set for post-generation guard: (meal_type, lower_name)
        existing_result = await db.execute(
            select(Recipe.meal_type, func.lower(Recipe.name)).where(Recipe.is_active == True)  # noqa
        )
        existing: set[tuple] = set(existing_result.fetchall())

        # Prompt context: {(meal_type, cuisine): [name, ...]} — passed to Claude
        names_result = await db.execute(
            select(Recipe.meal_type, Recipe.cuisine_region, Recipe.name)
            .where(Recipe.is_active == True)  # noqa
        )
        names_by_slot: dict[tuple, list[str]] = {}
        for mt, cr, nm in names_result.fetchall():
            names_by_slot.setdefault((mt, cr), []).append(nm)

        logger.info("Existing active recipes: %d", len(existing))

        for idx, (meal_type, cuisine, eating_mode, health_tags, count) in enumerate(GENERATION_MATRIX, 1):
            # ── Resume check: how many recipes already satisfy this entry? ──────
            already = await _count_existing(db, Recipe, meal_type, cuisine, eating_mode, health_tags)
            if already >= count:
                logger.info("[%d/%d] SKIP %s/%s/%s %s — already %d/%d",
                            idx, total_batches, meal_type, cuisine, eating_mode,
                            health_tags or "", already, count)
                total_batches_skipped += 1
                continue

            need = count - already
            prompt_existing = names_by_slot.get((meal_type, cuisine), [])
            logger.info("[%d/%d] %s/%s/%s %s  have=%d need=%d  context=%d names",
                        idx, total_batches, meal_type, cuisine, eating_mode,
                        health_tags or "", already, need, len(prompt_existing))

            try:
                recipes_data = await generate_recipe_batch(
                    meal_type=meal_type,
                    cuisine_region=cuisine,
                    eating_mode=eating_mode,
                    health_tags=health_tags,
                    count=need,
                    existing_names=prompt_existing,
                )
            except Exception as exc:
                logger.error("Batch failed: %s", exc)
                await asyncio.sleep(5)
                continue

            batch_inserted = 0
            for data in recipes_data:
                name_lower = (data.get("name") or "").strip().lower()
                if not name_lower:
                    continue
                key = (meal_type, name_lower)
                if key in existing:
                    total_skipped_dup += 1
                    continue
                existing.add(key)
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
                        is_verified=True,
                        is_active=True,
                        source="ai_generated",
                    )
                    db.add(recipe)
                    batch_inserted += 1
                except Exception as exc:
                    logger.warning("Skipping invalid recipe '%s': %s", data.get("name"), exc)

            await db.commit()
            total_inserted += batch_inserted
            logger.info("  +%d inserted (%d name-dups). Total: %d",
                        batch_inserted, total_skipped_dup, total_inserted)
            await asyncio.sleep(1)

    logger.info(
        "Seed complete. Inserted: %d  Batches skipped (already full): %d  Name-dups: %d",
        total_inserted, total_batches_skipped, total_skipped_dup,
    )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
