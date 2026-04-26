import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.admin import (
    CreateRecipeRequest, GenerateBatchResponse,
    RecipeListResponse, UserListResponse,
)
from app.schemas.recipe import RecipeOut

router = APIRouter()


@router.get("/recipes", response_model=RecipeListResponse)
async def list_recipes(
    is_verified: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Recipe)
        .where(Recipe.is_verified == is_verified)
        .where(Recipe.is_active == True)   # noqa: E712
        .order_by(Recipe.created_at.desc())
        .limit(limit)
    )
    recipes = result.scalars().all()
    return {"recipes": recipes, "total": len(recipes)}


@router.post("/recipes", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    request: CreateRecipeRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    recipe = Recipe(
        **request.model_dump(),
        is_verified=False,
        is_active=True,
        source="manual",
    )
    db.add(recipe)
    await db.commit()
    await db.refresh(recipe)
    return recipe


@router.patch("/recipes/{recipe_id}/verify", response_model=RecipeOut)
async def verify_recipe(
    recipe_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    recipe = await db.get(Recipe, uuid.UUID(recipe_id))
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    recipe.is_verified = True
    await db.commit()
    await db.refresh(recipe)
    return recipe


@router.patch("/recipes/{recipe_id}/reject")
async def reject_recipe(
    recipe_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    recipe = await db.get(Recipe, uuid.UUID(recipe_id))
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    recipe.is_active = False
    await db.commit()
    return {"message": "Recipe rejected and deactivated"}


@router.post("/recipes/generate-batch", response_model=GenerateBatchResponse)
async def generate_batch(current_user: User = Depends(get_current_admin)):
    # Full batch generation is run via the seed script; this endpoint triggers a small sample.
    return {
        "task_id": "use-seed-script",
        "message": "Run: python scripts/seed_recipes.py — or trigger specific batches via the AI Generate page",
    }


@router.get("/users", response_model=UserListResponse)
async def list_users(
    limit: int = 100,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()).limit(limit))
    users = result.scalars().all()
    return {"users": users, "total": len(users)}
