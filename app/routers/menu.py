import uuid
from datetime import date, datetime

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.dependencies import get_active_subscription, get_current_user, require_pro_plan
from app.models.daily_menu import DailyMenu
from app.models.recipe import Recipe
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.menu import (
    GroceryItem, GroceryListResponse, HistoryResponse, MenuInsightsResponse,
    MenuResponse, OverrideCuisineRequest, PDFURLResponse,
    RegenRequest, RegenerateResponse, TaskStatusResponse,
)
from app.utils.minio_client import get_presigned_url
from app.utils.redis_client import get_redis, regen_lock_key

router = APIRouter(prefix="/menu", tags=["menu"])

ALLOWED_CUISINES = {
    "north_indian", "south_indian", "bengali", "gujarati", "maharashtrian",
    "punjabi", "hyderabadi", "rajasthani", "kerala", "goan", "sattvic",
    "andhra", "tamil", "karnataka",
    "chinese", "italian", "continental",
}


async def _fetch_recipe(db: AsyncSession, recipe_id) -> Recipe | None:
    if not recipe_id:
        return None
    return await db.get(Recipe, recipe_id)


async def _enrich_menu(menu: DailyMenu, db: AsyncSession, user: User | None = None) -> dict:
    from app.services.nutrition_balance import compute_slot_serving, compute_daily_balance

    # Batch fetch all recipes in a single query (fixes N+1)
    slot_ids = {
        "breakfast":     menu.breakfast_id,
        "morning_snack": menu.morning_snack_id,
        "lunch":         menu.lunch_id,
        "evening_snack": menu.evening_snack_id,
        "dinner":        menu.dinner_id,
    }
    recipe_ids = [rid for rid in slot_ids.values() if rid is not None]
    recipe_map: dict = {}
    if recipe_ids:
        result = await db.execute(select(Recipe).where(Recipe.id.in_(recipe_ids)))
        for r in result.scalars().all():
            recipe_map[r.id] = r

    recipes = {slot: recipe_map.get(rid) for slot, rid in slot_ids.items()}

    pdf_url = None
    if menu.pdf_key:
        try:
            pdf_url = get_presigned_url(menu.pdf_key)
        except Exception:
            pdf_url = menu.pdf_url

    # Per-slot serving multipliers and scaled nutrition balance
    calorie_target  = int(user.daily_calorie_target or 2000) if user else 2000
    protein_target  = float(user.daily_protein_target_g or 50) if user else 50
    carbs_target    = float(user.daily_carbs_target_g or 250) if user else 250
    fat_target      = float(user.daily_fat_target_g or 55) if user else 55

    slot_servings: dict[str, dict] = {}
    for slot in slot_ids:
        recipe = recipes.get(slot)
        slot_servings[slot] = compute_slot_serving(recipe, slot, calorie_target) if recipe else {
            "multiplier": 1.0, "recommended_qty": "", "scaled_calories": 0
        }

    balance = compute_daily_balance(
        recipes, slot_servings,
        calorie_target, protein_target, carbs_target, fat_target,
    )

    return {
        "id": menu.id,
        "owner_id": menu.owner_id,
        "owner_type": menu.owner_type,
        "menu_date": menu.menu_date,
        "breakfast":     recipes["breakfast"],
        "morning_snack": recipes["morning_snack"],
        "lunch":         recipes["lunch"],
        "evening_snack": recipes["evening_snack"],
        "dinner":        recipes["dinner"],
        "total_calories": menu.total_calories,
        "total_protein_g": float(menu.total_protein_g or 0),
        "total_carbs_g": float(menu.total_carbs_g or 0),
        "total_fat_g": float(menu.total_fat_g or 0),
        # Per-slot serving guidance
        "breakfast_serving":     slot_servings["breakfast"],
        "morning_snack_serving": slot_servings["morning_snack"],
        "lunch_serving":         slot_servings["lunch"],
        "evening_snack_serving": slot_servings["evening_snack"],
        "dinner_serving":        slot_servings["dinner"],
        # Scaled daily totals
        "target_calories": calorie_target,
        **balance,
        "cuisine_override": menu.cuisine_override,
        "is_regenerated": menu.is_regenerated or False,
        "pdf_url": pdf_url,
        "wa_status": menu.wa_status,
    }


def _get_owner(user: User) -> tuple[str, str]:
    if user.household_id:
        return str(user.household_id), "household"
    return str(user.id), "user"


@router.get("/today", response_model=MenuResponse)
async def get_today_menu(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _sub: Subscription = Depends(get_active_subscription),
):
    owner_id, owner_type = _get_owner(current_user)
    result = await db.execute(
        select(DailyMenu).where(
            and_(
                DailyMenu.owner_id == uuid.UUID(owner_id),
                DailyMenu.owner_type == owner_type,
                DailyMenu.menu_date == date.today(),
            )
        )
    )
    menu = result.scalar_one_or_none()
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No menu for today yet. It will be generated at midnight.",
        )
    return await _enrich_menu(menu, db, user=current_user)


@router.get("/history", response_model=HistoryResponse)
async def get_menu_history(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _sub: Subscription = Depends(get_active_subscription),
):
    from datetime import timedelta
    owner_id, owner_type = _get_owner(current_user)
    cutoff = date.today() - timedelta(days=days)

    result = await db.execute(
        select(DailyMenu).where(
            and_(
                DailyMenu.owner_id == uuid.UUID(owner_id),
                DailyMenu.owner_type == owner_type,
                DailyMenu.menu_date >= cutoff,
            )
        ).order_by(DailyMenu.menu_date.desc())
    )
    menus = result.scalars().all()
    enriched = [await _enrich_menu(m, db) for m in menus]
    return {"menus": enriched}


@router.post("/regenerate", response_model=RegenerateResponse)
async def regenerate_menu(
    request: RegenRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _sub: Subscription = Depends(require_pro_plan),
):
    owner_id, owner_type = _get_owner(current_user)
    lock_key = regen_lock_key(owner_id)

    if await redis.exists(lock_key):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Menu regeneration already in progress. Try again in a few minutes.",
        )

    await redis.set(lock_key, "1", ex=300)

    cuisine_override = request.cuisine_override if request else None

    from app.tasks.menu_tasks import generate_single_menu
    task = generate_single_menu.delay(owner_id, owner_type, str(date.today()), cuisine_override)

    return RegenerateResponse(
        task_id=task.id,
        message="Regenerating your menu, check back in 2 minutes",
    )


@router.get("/regenerate/{task_id}", response_model=TaskStatusResponse)
async def get_regen_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    result = AsyncResult(task_id)
    if result.ready():
        if result.successful():
            return TaskStatusResponse(status="done", menu_date=str(date.today()))
        return TaskStatusResponse(status="failed", error=str(result.result))
    return TaskStatusResponse(status="pending")


@router.post("/override-cuisine", response_model=RegenerateResponse)
async def override_cuisine(
    request: OverrideCuisineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _sub: Subscription = Depends(require_pro_plan),
):
    if request.cuisine not in ALLOWED_CUISINES:
        raise HTTPException(
            status_code=400,
            detail=f"cuisine must be one of: {sorted(ALLOWED_CUISINES)}",
        )

    owner_id, owner_type = _get_owner(current_user)
    key = f"cuisine_override:{owner_id}:{date.today()}"
    await redis.set(key, request.cuisine, ex=86400)

    from app.tasks.menu_tasks import generate_single_menu
    task = generate_single_menu.delay(owner_id, owner_type, str(date.today()), request.cuisine)

    return RegenerateResponse(
        task_id=task.id,
        message=f"Generating menu with {request.cuisine} cuisine preference",
    )


VALID_SLOTS = {"breakfast", "morning_snack", "lunch", "evening_snack", "dinner"}


@router.patch("/today/{slot}/skip", status_code=200)
async def skip_slot(
    slot: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _sub: Subscription = Depends(get_active_subscription),
):
    """Clear a single meal slot from today's menu."""
    if slot not in VALID_SLOTS:
        raise HTTPException(status_code=400, detail=f"slot must be one of: {VALID_SLOTS}")

    owner_id, owner_type = _get_owner(current_user)
    result = await db.execute(
        select(DailyMenu).where(
            and_(
                DailyMenu.owner_id == uuid.UUID(owner_id),
                DailyMenu.owner_type == owner_type,
                DailyMenu.menu_date == date.today(),
            )
        )
    )
    menu = result.scalar_one_or_none()
    if not menu:
        raise HTTPException(status_code=404, detail="No menu for today")

    setattr(menu, f"{slot}_id", None)
    await db.flush()
    return {"message": f"{slot} skipped for today"}


@router.get("/today/insights", response_model=MenuInsightsResponse)
async def get_menu_insights(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _sub: Subscription = Depends(get_active_subscription),
):
    """Why was today's menu generated this way? Returns signals, candidate pool sizes, cuisine."""
    from app.services.menu_engine import get_menu_insights as _insights
    owner_id, owner_type = _get_owner(current_user)
    data = await _insights(db, redis, owner_id, owner_type, date.today())
    return MenuInsightsResponse(**data)


@router.get("/{menu_date}/grocery-list", response_model=GroceryListResponse)
async def get_grocery_list(
    menu_date: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _sub: Subscription = Depends(get_active_subscription),
):
    try:
        parsed_date = date.fromisoformat(menu_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    owner_id, owner_type = _get_owner(current_user)
    result = await db.execute(
        select(DailyMenu).where(
            and_(
                DailyMenu.owner_id == uuid.UUID(owner_id),
                DailyMenu.owner_type == owner_type,
                DailyMenu.menu_date == parsed_date,
            )
        )
    )
    menu = result.scalar_one_or_none()
    if not menu:
        raise HTTPException(status_code=404, detail="No menu for this date")

    recipes = {
        "breakfast":     await _fetch_recipe(db, menu.breakfast_id),
        "morning_snack": await _fetch_recipe(db, menu.morning_snack_id),
        "lunch":         await _fetch_recipe(db, menu.lunch_id),
        "evening_snack": await _fetch_recipe(db, menu.evening_snack_id),
        "dinner":        await _fetch_recipe(db, menu.dinner_id),
    }
    recipe_count = sum(1 for r in recipes.values() if r is not None)

    member_count = 1
    if owner_type == "household":
        from app.models.household_member import HouseholdMember as HHMember
        from app.services.menu_engine import _child_weight
        user_result = await db.execute(
            select(User).where(User.household_id == uuid.UUID(owner_id))
        )
        hm_result = await db.execute(
            select(HHMember).where(HHMember.household_id == uuid.UUID(owner_id))
        )
        user_members = user_result.scalars().all()
        hh_members   = hm_result.scalars().all()
        adult_equiv  = float(len(user_members))
        adult_equiv += sum(_child_weight(m) for m in hh_members)
        member_count = max(1, round(adult_equiv))

    from app.services.grocery_service import build_grocery_list
    items = build_grocery_list(recipes, member_count)

    return GroceryListResponse(
        date=parsed_date,
        items=[GroceryItem(**item) for item in items],
        recipe_count=recipe_count,
        member_count=member_count,
    )


@router.get("/{menu_date}/pdf-url", response_model=PDFURLResponse)
async def get_pdf_url(
    menu_date: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _sub: Subscription = Depends(get_active_subscription),
):
    try:
        parsed_date = date.fromisoformat(menu_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    owner_id, owner_type = _get_owner(current_user)
    result = await db.execute(
        select(DailyMenu).where(
            and_(
                DailyMenu.owner_id == uuid.UUID(owner_id),
                DailyMenu.owner_type == owner_type,
                DailyMenu.menu_date == parsed_date,
            )
        )
    )
    menu = result.scalar_one_or_none()
    if not menu or not menu.pdf_key:
        raise HTTPException(status_code=404, detail="PDF not yet generated for this date")

    from app.config import settings
    pdf_url = get_presigned_url(menu.pdf_key)
    return PDFURLResponse(pdf_url=pdf_url, expires_in_hours=settings.PDF_PRESIGNED_URL_EXPIRE_HOURS)
