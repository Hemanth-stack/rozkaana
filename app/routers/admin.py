import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.daily_menu import DailyMenu
from app.models.recipe import Recipe
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.admin import (
    CreateRecipeRequest, DashboardStats, GenerateBatchRequest,
    GenerateBatchResponse, MenuAdminItem, MenuAdminListResponse,
    PipelineStatus, PipelineStep, RecipeListResponse, UserListResponse,
)
from app.schemas.recipe import RecipeOut, RecipeUpdate
from app.services.recipe_ai_generator import generate_recipe_batch

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/recipes", response_model=RecipeListResponse)
async def list_recipes(
    is_verified: bool = False,
    meal_type: str | None = None,
    cuisine_region: str | None = None,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    filters = [Recipe.is_verified == is_verified, Recipe.is_active == True]  # noqa: E712
    if meal_type:
        filters.append(Recipe.meal_type == meal_type)
    if cuisine_region:
        filters.append(Recipe.cuisine_region == cuisine_region)

    count_result = await db.execute(select(func.count()).select_from(Recipe).where(and_(*filters)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Recipe).where(and_(*filters))
        .order_by(Recipe.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    recipes = result.scalars().all()
    return RecipeListResponse(recipes=recipes, total=total, page=page, limit=limit)


@router.post("/recipes", response_model=RecipeOut, status_code=201)
async def create_recipe(
    request: CreateRecipeRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    recipe = Recipe(**request.model_dump(), is_verified=False, is_active=True, source="manual")
    db.add(recipe)
    await db.flush()
    await db.refresh(recipe)
    return recipe


@router.get("/recipes/{recipe_id}", response_model=RecipeOut)
async def get_recipe(
    recipe_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    recipe = await db.get(Recipe, uuid.UUID(recipe_id))
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.put("/recipes/{recipe_id}", response_model=RecipeOut)
async def update_recipe(
    recipe_id: str,
    request: RecipeUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    recipe = await db.get(Recipe, uuid.UUID(recipe_id))
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    for field, value in request.model_dump(exclude_none=True).items():
        setattr(recipe, field, value)
    await db.flush()
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
        raise HTTPException(status_code=404, detail="Recipe not found")
    recipe.is_verified = True
    recipe.is_active = True
    await db.flush()
    await db.refresh(recipe)
    return recipe


@router.patch("/recipes/{recipe_id}/reject", response_model=RecipeOut)
async def reject_recipe(
    recipe_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    recipe = await db.get(Recipe, uuid.UUID(recipe_id))
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    recipe.is_active = False
    await db.flush()
    await db.refresh(recipe)
    return recipe


@router.delete("/recipes/{recipe_id}", status_code=204)
async def delete_recipe(
    recipe_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    recipe = await db.get(Recipe, uuid.UUID(recipe_id))
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    recipe.is_active = False
    await db.flush()


@router.post("/recipes/generate-batch", response_model=GenerateBatchResponse)
async def generate_batch(
    request: GenerateBatchRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    recipes_data = await generate_recipe_batch(
        meal_type=request.meal_type,
        cuisine_region=request.cuisine_region,
        eating_mode=request.eating_mode,
        health_tags=request.health_tags,
        count=request.count,
    )
    inserted = []
    for data in recipes_data:
        recipe = Recipe(
            **{k: v for k, v in data.items() if hasattr(Recipe, k)},
            is_verified=False,
            is_active=True,
            source="ai_generated",
        )
        db.add(recipe)
        inserted.append(recipe)
    await db.flush()
    for r in inserted:
        await db.refresh(r)
    return GenerateBatchResponse(generated=len(inserted), recipes=inserted)


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = 1,
    limit: int = 20,
    plan_type: str | None = None,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(select(func.count()).select_from(User))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(User).order_by(User.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    users = result.scalars().all()
    return UserListResponse(users=users, total=total, page=page, limit=limit)


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sub_result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = sub_result.scalar_one_or_none()

    menu_result = await db.execute(
        select(DailyMenu).where(DailyMenu.owner_id == user.id)
        .order_by(DailyMenu.menu_date.desc())
        .limit(7)
    )
    recent_menus = menu_result.scalars().all()

    return {
        "user": user,
        "subscription": sub,
        "recent_menus": recent_menus,
    }


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0

    active_subs = (
        await db.execute(
            select(func.count()).select_from(Subscription)
            .where(Subscription.status.in_(["trial", "active"]))
        )
    ).scalar() or 0

    menus_today = (
        await db.execute(
            select(func.count()).select_from(DailyMenu)
            .where(DailyMenu.menu_date == today)
        )
    ).scalar() or 0

    pdfs_today = (
        await db.execute(
            select(func.count()).select_from(DailyMenu)
            .where(and_(DailyMenu.menu_date == today, DailyMenu.pdf_key.isnot(None)))
        )
    ).scalar() or 0

    wa_delivered = (
        await db.execute(
            select(func.count()).select_from(DailyMenu)
            .where(and_(DailyMenu.menu_date == today, DailyMenu.wa_status == "delivered"))
        )
    ).scalar() or 0

    wa_failed = (
        await db.execute(
            select(func.count()).select_from(DailyMenu)
            .where(and_(DailyMenu.menu_date == today, DailyMenu.wa_status == "failed"))
        )
    ).scalar() or 0

    active_sub_rows = (
        await db.execute(
            select(Subscription.plan_type).where(Subscription.status == "active")
        )
    ).scalars().all()

    from app.schemas.admin import PLAN_PRICES
    plan_prices = {"solo_basic": 299.0, "solo_pro": 499.0, "family": 799.0}
    mrr = sum(plan_prices.get(pt, 0) for pt in active_sub_rows)

    plan_distribution: dict[str, int] = {}
    for pt in active_sub_rows:
        plan_distribution[pt] = plan_distribution.get(pt, 0) + 1

    return DashboardStats(
        total_users=total_users,
        active_subscribers=active_subs,
        menus_today=menus_today,
        pdfs_built_today=pdfs_today,
        wa_delivered_today=wa_delivered,
        wa_failed_today=wa_failed,
        mrr=mrr,
        plan_distribution=plan_distribution,
    )


@router.get("/pipeline/today", response_model=PipelineStatus)
async def pipeline_today(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()

    active_subs = (
        await db.execute(
            select(func.count()).select_from(Subscription)
            .where(Subscription.status.in_(["trial", "active"]))
        )
    ).scalar() or 0

    menus_gen = (
        await db.execute(select(func.count()).select_from(DailyMenu).where(DailyMenu.menu_date == today))
    ).scalar() or 0

    pdfs_built = (
        await db.execute(
            select(func.count()).select_from(DailyMenu)
            .where(and_(DailyMenu.menu_date == today, DailyMenu.pdf_key.isnot(None)))
        )
    ).scalar() or 0

    wa_sent = (
        await db.execute(
            select(func.count()).select_from(DailyMenu)
            .where(and_(DailyMenu.menu_date == today, DailyMenu.wa_sent_at.isnot(None)))
        )
    ).scalar() or 0

    wa_failed = (
        await db.execute(
            select(func.count()).select_from(DailyMenu)
            .where(and_(DailyMenu.menu_date == today, DailyMenu.wa_status == "failed"))
        )
    ).scalar() or 0

    steps = [
        PipelineStep(name="Menu Generation", count=active_subs, completed=menus_gen, failed=active_subs - menus_gen, status="done" if menus_gen >= active_subs else "partial"),
        PipelineStep(name="PDF Build", count=menus_gen, completed=pdfs_built, failed=menus_gen - pdfs_built, status="done" if pdfs_built >= menus_gen else "partial"),
        PipelineStep(name="WhatsApp Delivery", count=pdfs_built, completed=wa_sent, failed=wa_failed, status="done" if wa_sent >= pdfs_built else "partial"),
    ]
    return PipelineStatus(date=today, steps=steps)


@router.get("/menus", response_model=MenuAdminListResponse)
async def list_menus(
    menu_date: str | None = None,
    owner_id: str | None = None,
    wa_status: str | None = None,
    page: int = 1,
    limit: int = 50,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if menu_date:
        try:
            filters.append(DailyMenu.menu_date == date.fromisoformat(menu_date))
        except ValueError:
            pass
    if owner_id:
        try:
            filters.append(DailyMenu.owner_id == uuid.UUID(owner_id))
        except ValueError:
            pass
    if wa_status:
        filters.append(DailyMenu.wa_status == wa_status)

    count_q = select(func.count()).select_from(DailyMenu)
    if filters:
        count_q = count_q.where(and_(*filters))
    total = (await db.execute(count_q)).scalar() or 0

    q = select(DailyMenu).order_by(DailyMenu.generated_at.desc()).offset((page - 1) * limit).limit(limit)
    if filters:
        q = q.where(and_(*filters))
    menus = (await db.execute(q)).scalars().all()

    items = []
    for m in menus:
        owner_name = None
        if m.owner_type == "user":
            u = await db.get(User, m.owner_id)
            owner_name = u.name if u else None
        items.append(MenuAdminItem(
            id=m.id, owner_id=m.owner_id, owner_type=m.owner_type,
            menu_date=m.menu_date, pdf_key=m.pdf_key, wa_status=m.wa_status,
            wa_sent_at=m.wa_sent_at, generated_at=m.generated_at, owner_name=owner_name,
        ))

    return MenuAdminListResponse(menus=items, total=total)


@router.post("/menus/{menu_id}/retry-wa", status_code=202)
async def retry_wa(
    menu_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    menu = await db.get(DailyMenu, uuid.UUID(menu_id))
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")
    from app.tasks.wa_tasks import send_single_whatsapp
    task = send_single_whatsapp.delay(menu_id)
    return {"task_id": task.id, "message": "WhatsApp retry queued"}


@router.get("/logs")
async def get_logs(
    log_date: str | None = None,
    level: str | None = None,
    page: int = 1,
    limit: int = 100,
    current_user: User = Depends(get_current_admin),
):
    return {
        "logs": [],
        "total": 0,
        "message": "Structured logging via systemd journal. Use: journalctl -u nutriseva-api --since today",
    }
