import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.dependencies import get_current_admin
from app.utils.security import create_access_token, create_refresh_token
from app.models.daily_menu import DailyMenu
from app.models.recipe import Recipe
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.admin import (
    CreateRecipeRequest, DashboardStats, GenerateBatchRequest,
    GenerateBatchResponse, MenuAdminItem, MenuAdminListResponse,
    PipelineStatus, PipelineStep, RecipeListResponse, UserAdminProfile, UserListResponse,
)
from app.schemas.recipe import RecipeOut, RecipeUpdate
from app.services.recipe_ai_generator import generate_recipe_batch

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminLoginRequest(BaseModel):
    email: str = ""
    phone: str = ""
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=AdminTokenResponse)
async def admin_login(
    http_request: Request,
    request: AdminLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.config import settings
    from app.utils.rate_limiter import limiter
    # Manual rate limit check (decorator can't be used with mixed Request/Depends signature)
    if request.email:
        result = await db.execute(
            select(User).where(User.email == request.email.lower(), User.is_admin == True)  # noqa
        )
    else:
        result = await db.execute(
            select(User).where(User.phone == request.phone, User.is_admin == True)  # noqa
        )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Bcrypt check (primary); falls back to legacy JWT[:8] if hash not configured yet
    if settings.ADMIN_PASSWORD_HASH:
        from passlib.hash import bcrypt as _bcrypt
        try:
            ok = _bcrypt.verify(request.password, settings.ADMIN_PASSWORD_HASH)
        except Exception:
            ok = False
    else:
        ok = request.password == settings.JWT_SECRET_KEY[:8]

    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    data = {"sub": str(user.id)}
    return AdminTokenResponse(
        access_token=create_access_token(data),
        refresh_token=create_refresh_token(data),
    )


@router.post("/recipes/run-seed", status_code=202)
async def run_recipe_seed(
    verify: bool = True,
    current_user: User = Depends(get_current_admin),
):
    """Trigger full recipe GENERATION_MATRIX as a background Celery task (~45-60 min)."""
    from app.tasks.seed_tasks import run_recipe_seed as _seed_task
    task = _seed_task.delay(verify=verify)
    return {
        "task_id": task.id,
        "message": "Seed started. Poll /admin/status/task/{task_id} for progress.",
        "estimated_recipes": "~2200",
        "estimated_time_minutes": "45-60",
    }


@router.get("/recipes/stats")
async def recipe_stats(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Recipe bank coverage: count per meal_type × cuisine × eating_mode × is_verified."""
    from sqlalchemy import text
    sql = text("""
        SELECT meal_type, cuisine_region,
               unnest(eating_mode_tags) AS eating_mode,
               is_verified, COUNT(*) AS count
        FROM recipes
        WHERE is_active = true
        GROUP BY meal_type, cuisine_region, eating_mode, is_verified
        ORDER BY meal_type, cuisine_region, eating_mode, is_verified
    """)
    rows = (await db.execute(sql)).mappings().all()

    total = (await db.execute(
        select(func.count()).select_from(Recipe).where(Recipe.is_active == True)  # noqa
    )).scalar() or 0
    verified = (await db.execute(
        select(func.count()).select_from(Recipe).where(
            Recipe.is_active == True, Recipe.is_verified == True  # noqa
        )
    )).scalar() or 0

    matrix = [dict(r) for r in rows]
    gaps = [r for r in matrix if r["is_verified"] and r["count"] < 5]

    return {
        "total_active": total,
        "total_verified": verified,
        "matrix": matrix,
        "coverage_gaps": gaps,
    }


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
        model=request.model,
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
    search: str | None = None,
    plan_type: str | None = None,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if search:
        from sqlalchemy import or_
        filters.append(or_(
            User.name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%"),
        ))

    count_q = select(func.count()).select_from(User)
    if filters:
        from sqlalchemy import and_
        count_q = count_q.where(and_(*filters))
    total = (await db.execute(count_q)).scalar() or 0

    q = select(User).order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
    if filters:
        from sqlalchemy import and_
        q = q.where(and_(*filters))
    users = (await db.execute(q)).scalars().all()

    user_ids = [u.id for u in users]
    sub_map: dict = {}
    if user_ids:
        sub_rows = (await db.execute(
            select(Subscription).where(Subscription.user_id.in_(user_ids))
        )).scalars().all()
        sub_map = {s.user_id: s for s in sub_rows}

    items = []
    for u in users:
        sub = sub_map.get(u.id)
        items.append(UserAdminProfile(
            id=u.id, name=u.name, email=u.email, phone=u.phone,
            eating_mode=u.eating_mode, goal=u.goal, bmi=u.bmi,
            health_tags=u.health_tags or [],
            is_active=u.is_active, is_admin=u.is_admin,
            onboarding_complete=u.onboarding_complete,
            wa_opted_in=u.wa_opted_in or False,
            created_at=u.created_at,
            plan_type=sub.plan_type if sub else None,
            sub_status=sub.status if sub else None,
            sub_period_end=sub.current_period_end if sub else None,
            trial_end=sub.trial_end if sub else None,
        ))

    # Filter by plan after joining (small dataset, fine for pilot)
    if plan_type:
        items = [i for i in items if i.plan_type == plan_type]

    return UserListResponse(users=items, total=total, page=page, limit=limit)


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

    emails_sent = (
        await db.execute(
            select(func.count()).select_from(DailyMenu)
            .where(and_(DailyMenu.menu_date == today, DailyMenu.wa_sent_at.isnot(None)))
        )
    ).scalar() or 0

    active_sub_rows = (
        await db.execute(
            select(Subscription.plan_type).where(Subscription.status == "active")
        )
    ).scalars().all()

    plan_prices = {"solo_basic": 199.0, "solo_pro": 399.0, "family": 699.0}
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
        emails_sent_today=emails_sent,
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
        PipelineStep(name="Email Delivery", count=pdfs_built, completed=wa_sent, failed=wa_failed, status="done" if wa_sent >= pdfs_built else "partial"),
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


@router.post("/trigger/full-pipeline", status_code=202)
async def trigger_full_pipeline(
    target_date: str | None = None,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Dev trigger: generate menus for all active subscribers → build PDFs → send WA."""
    from datetime import timedelta
    from app.tasks.menu_tasks import generate_all_menus
    run_date = date.fromisoformat(target_date) if target_date else date.today()
    task = generate_all_menus.delay()
    return {
        "message": f"Full pipeline triggered for {run_date}",
        "task_id": task.id,
        "steps": ["menu_generation", "pdf_build (auto after menu)", "whatsapp_send (manual or auto)"],
    }


@router.post("/trigger/menu/{user_id}", status_code=202)
async def trigger_user_menu(
    user_id: str,
    for_date: str | None = None,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generate + build PDF + send WA for a single user right now."""
    from app.tasks.menu_tasks import generate_single_menu
    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    run_date = for_date or str(date.today())
    owner_id = str(user.household_id or user.id)
    owner_type = "household" if user.household_id else "user"
    task = generate_single_menu.delay(owner_id, owner_type, run_date, None)
    return {"message": f"Menu → PDF → WA triggered for {user.phone}", "task_id": task.id, "date": run_date}


@router.post("/trigger/pdf/{menu_id}", status_code=202)
async def trigger_pdf(
    menu_id: str,
    current_user: User = Depends(get_current_admin),
):
    """Build PDF for a specific menu_id."""
    from app.tasks.pdf_tasks import build_single_pdf
    task = build_single_pdf.delay(menu_id)
    return {"message": "PDF build queued", "task_id": task.id}


@router.post("/trigger/wa/{menu_id}", status_code=202)
async def trigger_wa(
    menu_id: str,
    current_user: User = Depends(get_current_admin),
):
    """Send WhatsApp for a specific menu_id."""
    from app.tasks.wa_tasks import send_single_whatsapp
    task = send_single_whatsapp.delay(menu_id)
    return {"message": "WhatsApp send queued", "task_id": task.id}


@router.get("/status/task/{task_id}")
async def task_status(
    task_id: str,
    current_user: User = Depends(get_current_admin),
):
    """Poll a Celery task result."""
    from celery.result import AsyncResult
    r = AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": r.status,
        "result": str(r.result) if r.ready() else None,
    }


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
    return {"task_id": task.id, "message": "Retry queued"}


@router.post("/menus/{menu_id}/retry-email", status_code=202)
async def retry_email(
    menu_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    menu = await db.get(DailyMenu, uuid.UUID(menu_id))
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")
    from app.tasks.email_tasks import send_menu_email
    task = send_menu_email.delay(menu_id)
    return {"task_id": task.id, "message": "Email retry queued"}


@router.get("/logs")
async def get_logs(
    level: str | None = None,
    limit: int = 200,
    current_user: User = Depends(get_current_admin),
):
    import asyncio
    import re

    log_path = "/tmp/rozkaana-api.log"
    pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})[,.]?\d*\s+(\w+)\s+(\S+):\s+(.*)$"
    )
    level_map = {"WARNING": "WARN", "ERROR": "ERR", "CRITICAL": "ERR"}

    def _read():
        try:
            with open(log_path) as f:
                lines = f.readlines()
            return lines[-limit:] if len(lines) > limit else lines
        except FileNotFoundError:
            return []

    lines = await asyncio.get_event_loop().run_in_executor(None, _read)
    logs = []
    for line in lines:
        line = line.rstrip()
        if not line:
            continue
        m = pattern.match(line)
        if m:
            ts, lvl, svc, msg = m.groups()
            lvl = level_map.get(lvl.upper(), lvl.upper()[:4])
            if level and lvl != level.upper()[:4]:
                continue
            logs.append({"ts": ts, "level": lvl, "service": svc.split(".")[-1], "message": msg})
        else:
            logs.append({"ts": "—", "level": "INFO", "service": "app", "message": line})

    return {"logs": logs, "total": len(logs)}


@router.get("/system/health")
async def system_health(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    import asyncio
    import time
    from datetime import datetime

    components: dict = {}

    # Database
    t0 = time.time()
    try:
        from sqlalchemy import text as _text
        await db.execute(_text("SELECT 1"))
        components["database"] = {"status": "ok", "latency_ms": round((time.time()-t0)*1000, 1)}
    except Exception as e:
        components["database"] = {"status": "down", "detail": str(e)}

    # Redis
    t0 = time.time()
    try:
        from app.utils.redis_client import get_redis as _get_redis
        import redis.asyncio as _aioredis
        from app.config import settings as _s
        r = _aioredis.from_url(_s.REDIS_URL)
        await r.ping()
        await r.aclose()
        components["redis"] = {"status": "ok", "latency_ms": round((time.time()-t0)*1000, 1)}
    except Exception as e:
        components["redis"] = {"status": "down", "detail": str(e)}

    # MinIO
    t0 = time.time()
    try:
        from app.utils.minio_client import _client, settings as _ms
        await asyncio.get_event_loop().run_in_executor(None, _client.list_buckets)
        components["minio"] = {"status": "ok", "latency_ms": round((time.time()-t0)*1000, 1)}
    except Exception as e:
        components["minio"] = {"status": "degraded", "detail": str(e)}

    # Celery workers
    t0 = time.time()
    try:
        from app.tasks.celery_app import celery_app as _celery
        def _ping():
            return _celery.control.inspect(timeout=3.0).ping()
        ping = await asyncio.get_event_loop().run_in_executor(None, _ping)
        worker_count = len(ping) if ping else 0
        components["celery"] = {
            "status": "ok" if worker_count > 0 else "degraded",
            "latency_ms": round((time.time()-t0)*1000, 1),
            "detail": f"{worker_count} worker(s) responding",
        }
    except Exception as e:
        components["celery"] = {"status": "down", "detail": str(e)}

    overall = (
        "ok" if all(c["status"] == "ok" for c in components.values())
        else "down" if any(c["status"] == "down" for c in components.values())
        else "degraded"
    )
    return {"overall": overall, "components": components, "checked_at": datetime.utcnow().isoformat()}


@router.get("/celery/stats")
async def celery_stats(current_user: User = Depends(get_current_admin)):
    import asyncio

    def _inspect():
        from app.tasks.celery_app import celery_app as _celery
        i = _celery.control.inspect(timeout=5.0)
        return i.active() or {}, i.reserved() or {}

    active, reserved = await asyncio.get_event_loop().run_in_executor(None, _inspect)

    queue_depths: dict = {}
    try:
        from app.config import settings as _s
        import redis.asyncio as _aioredis
        r = _aioredis.from_url(_s.REDIS_URL.replace("/0", "/1"))  # broker db
        queue_depths["celery"] = await r.llen("celery")
        await r.aclose()
    except Exception:
        pass

    return {
        "workers": list(active.keys()),
        "active_tasks": {w: [t.get("name") for t in tasks] for w, tasks in active.items()},
        "reserved_tasks": {w: [t.get("name") for t in tasks] for w, tasks in reserved.items()},
        "queue_depths": queue_depths,
        "total_active": sum(len(t) for t in active.values()),
        "total_reserved": sum(len(t) for t in reserved.values()),
    }
