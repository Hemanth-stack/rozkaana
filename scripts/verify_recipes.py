"""
CLI tool for nutritionist to review and verify/reject recipes.
Run: python -m scripts.verify_recipes
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select


async def main():
    from app.config import settings
    from app.models.recipe import Recipe

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    page_size = 10
    verified_count = rejected_count = skipped_count = 0

    async with AsyncSessionLocal() as db:
        while True:
            result = await db.execute(
                select(Recipe)
                .where(Recipe.is_verified == False, Recipe.is_active == True)  # noqa: E712
                .order_by(Recipe.created_at)
                .limit(page_size)
            )
            recipes = result.scalars().all()

            if not recipes:
                print(f"\nNo more recipes to review.")
                break

            for recipe in recipes:
                print("\n" + "=" * 60)
                print(f"  ID:          {recipe.id}")
                print(f"  Name:        {recipe.name}")
                print(f"  Local Name:  {recipe.name_local or '—'}")
                print(f"  Meal Type:   {recipe.meal_type}")
                print(f"  Cuisine:     {recipe.cuisine_region}")
                print(f"  Eating Mode: {recipe.eating_mode_tags}")
                print(f"  Health Tags: {recipe.health_safe_tags}")
                print(f"  Macros:      {recipe.calories} kcal | P: {recipe.protein_g}g | C: {recipe.carbs_g}g | F: {recipe.fat_g}g | Fibre: {recipe.fibre_g}g")
                print(f"  Serving:     {recipe.serving_unit}")
                print(f"  Prep Time:   {recipe.prep_time_mins} mins")
                print(f"  Spice:       {recipe.spice_level}")
                print(f"  Main Ing:    {recipe.main_ingredient}")
                print(f"\n  Ingredients:")
                for ing in (recipe.ingredients or []):
                    flag = " (per person)" if ing.get("per_person") else ""
                    print(f"    - {ing.get('qty')} {ing.get('unit')} {ing.get('name')}{flag}")
                print(f"\n  Steps:")
                for i, step in enumerate(recipe.steps or [], 1):
                    print(f"    {i}. {step}")
                print()

                while True:
                    choice = input("  [v]erify / [r]eject / [s]kip / [q]uit: ").strip().lower()
                    if choice in ("v", "r", "s", "q"):
                        break
                    print("  Invalid input. Enter v, r, s, or q.")

                if choice == "q":
                    print(f"\nExiting. Verified: {verified_count}, Rejected: {rejected_count}, Skipped: {skipped_count}")
                    await db.commit()
                    await engine.dispose()
                    return

                elif choice == "v":
                    recipe.is_verified = True
                    recipe.is_active = True
                    verified_count += 1
                    print(f"  ✓ Verified")

                elif choice == "r":
                    recipe.is_active = False
                    rejected_count += 1
                    print(f"  ✗ Rejected")

                elif choice == "s":
                    skipped_count += 1
                    print(f"  → Skipped")

            await db.commit()
            print(f"\n--- Progress: Verified {verified_count} | Rejected {rejected_count} | Skipped {skipped_count} ---")

    print(f"\nDone. Verified: {verified_count}, Rejected: {rejected_count}, Skipped: {skipped_count}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
