import asyncio
import logging
from app.services.recipe_ai_generator import generate_recipe_batch
from app.models.recipe import Recipe
from app.database import engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)

GENERATION_MATRIX = [
    ("breakfast", "north_indian", "pure_veg", [], 10),
    ("breakfast", "south_indian", "pure_veg", [], 10),
    ("breakfast", "north_indian", "pure_veg", ["diabetes_t2"], 8),
    ("lunch", "north_indian", "pure_veg", [], 15),
    ("lunch", "north_indian", "full_nv", [], 10),
    ("lunch", "hyderabadi", "full_nv", [], 8),
    ("dinner", "north_indian", "pure_veg", [], 12),
    ("dinner", "south_indian", "pure_veg", [], 10),
    ("snack", "north_indian", "pure_veg", [], 15),
]

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def main():
    async with AsyncSessionLocal() as db:
        for args in GENERATION_MATRIX:
            meal_type, cuisine_region, eating_mode, health_tags, count = args
            recipes = await generate_recipe_batch(
                meal_type,
                cuisine_region,
                eating_mode,
                health_tags=health_tags,
                count=count,
            )
            logging.info("Generated %s recipes for %s", len(recipes), args)
            for recipe_data in recipes:
                recipe = Recipe(
                    name=recipe_data["name"],
                    name_local=recipe_data.get("name_local"),
                    meal_type=recipe_data["meal_type"],
                    cuisine_region=recipe_data["cuisine_region"],
                    eating_mode_tags=recipe_data.get("eating_mode_tags", []),
                    health_safe_tags=recipe_data.get("health_safe_tags", []),
                    allergy_free_tags=recipe_data.get("allergy_free_tags", []),
                    calories=recipe_data.get("calories"),
                    protein_g=recipe_data.get("protein_g"),
                    carbs_g=recipe_data.get("carbs_g"),
                    fat_g=recipe_data.get("fat_g"),
                    fibre_g=recipe_data.get("fibre_g"),
                    serving_unit=recipe_data.get("serving_unit"),
                    prep_time_mins=recipe_data.get("prep_time_mins"),
                    spice_level=recipe_data.get("spice_level"),
                    main_ingredient=recipe_data.get("main_ingredient"),
                    ingredients=recipe_data.get("ingredients", []),
                    steps=recipe_data.get("steps", []),
                    is_verified=False,
                    is_active=True,
                    source="ai_generated",
                )
                db.add(recipe)
            await db.commit()
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())