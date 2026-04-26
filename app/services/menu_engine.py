import time
import uuid
from datetime import date
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.daily_menu import DailyMenu
from app.models.household import Household
from app.models.recipe import Recipe
from app.models.user import User
from app.utils.festival_calendar import get_festival, FESTIVAL_CUISINE_MAP

SLOT_RATIOS: dict[str, float] = {
    "breakfast": 0.25,
    "morning_snack": 0.10,
    "lunch": 0.35,
    "evening_snack": 0.10,
    "dinner": 0.20,
}

DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

ALL_CUISINES = [
    "north_indian", "south_indian", "bengali", "gujarati", "maharashtrian",
    "punjabi", "hyderabadi", "rajasthani", "kerala", "goan", "sattvic",
]

EATING_MODE_STRICTNESS = {
    "jain": 0,
    "sattvic": 1,
    "pure_veg": 2,
    "conditional_nv": 3,
    "full_nv": 4,
}


async def generate_menu(
    db: AsyncSession,
    redis: Redis,
    owner_id: str,
    owner_type: str,
    menu_date: date,
    cuisine_override: str | None = None,
) -> dict:
    ctx = await _load_context(db, owner_id, owner_type, menu_date)

    excluded = await _get_excluded_ids(redis, owner_id)

    cuisine_override = cuisine_override or await _get_cuisine_override(redis, owner_id, str(menu_date))
    cuisine_pool = _resolve_cuisine(ctx, menu_date, cuisine_override)

    slots = list(SLOT_RATIOS.keys())
    candidates: dict[str, list[Recipe]] = {}
    for slot in slots:
        candidates[slot] = await _query_candidates(db, slot, ctx, excluded.get(slot, set()), cuisine_pool)

    selected = _select_by_macro(candidates, ctx)
    selected = _apply_variety_rules(selected, candidates)

    await _update_history(redis, owner_id, selected)

    return _build_menu_record(selected, menu_date, owner_id, owner_type, cuisine_override)


async def _load_context(db: AsyncSession, owner_id: str, owner_type: str, menu_date: date) -> dict:
    if owner_type == "user":
        user = await db.get(User, uuid.UUID(owner_id))
        if not user:
            raise ValueError(f"User {owner_id} not found")
        eating_mode = user.eating_mode or "pure_veg"
        health_tags = user.health_tags or []
        allergy_tags = user.allergy_tags or []
        cuisine_prefs = user.cuisine_prefs or ["north_indian"]
        calorie_target = user.daily_calorie_target or 2000
        nv_days = user.nv_days or []
        member_count = 1
        macro_targets = {
            "calories": calorie_target,
            "protein_g": float(user.daily_protein_target_g or calorie_target * 0.25 / 4),
            "carbs_g": float(user.daily_carbs_target_g or calorie_target * 0.50 / 4),
            "fat_g": float(user.daily_fat_target_g or calorie_target * 0.25 / 9),
        }
    else:
        household = await db.get(Household, uuid.UUID(owner_id))
        if not household:
            raise ValueError(f"Household {owner_id} not found")
        result = await db.execute(select(User).where(User.household_id == uuid.UUID(owner_id)))
        members = result.scalars().all()
        if not members:
            raise ValueError(f"Household {owner_id} has no members")

        all_eating_modes = [m.eating_mode or "pure_veg" for m in members]
        eating_mode = min(all_eating_modes, key=lambda m: EATING_MODE_STRICTNESS.get(m, 99))

        health_tags = list(set(tag for m in members for tag in (m.health_tags or [])))
        allergy_tags = list(set(tag for m in members for tag in (m.allergy_tags or [])))
        cuisine_prefs = household.cuisine_prefs or ["north_indian"]
        head = next((m for m in members if m.is_household_head), members[0])
        calorie_target = head.daily_calorie_target or 2000
        nv_days = []
        member_count = len(members)
        macro_targets = {
            "calories": calorie_target,
            "protein_g": float(head.daily_protein_target_g or calorie_target * 0.25 / 4),
            "carbs_g": float(head.daily_carbs_target_g or calorie_target * 0.50 / 4),
            "fat_g": float(head.daily_fat_target_g or calorie_target * 0.25 / 9),
        }

    today_name = DAY_NAMES[menu_date.weekday()]
    is_nv_day = today_name in [d.lower() for d in nv_days]

    festival_name = get_festival(menu_date)

    return {
        "eating_mode": eating_mode,
        "health_tags": health_tags,
        "allergy_tags": allergy_tags,
        "cuisine_prefs": cuisine_prefs,
        "calorie_target": calorie_target,
        "macro_targets": macro_targets,
        "is_nv_day": is_nv_day,
        "is_festival": festival_name is not None,
        "festival_name": festival_name,
        "member_count": member_count,
    }


async def _get_excluded_ids(redis: Redis, owner_id: str) -> dict[str, set]:
    excluded: dict[str, set] = {}
    cutoff = time.time() - (7 * 24 * 3600)
    for slot in SLOT_RATIOS:
        key = f"menu_history:{owner_id}:{slot}"
        ids = await redis.zrangebyscore(key, cutoff, "+inf")
        excluded[slot] = set(ids)
    return excluded


async def _get_cuisine_override(redis: Redis, owner_id: str, date_str: str) -> str | None:
    key = f"cuisine_override:{owner_id}:{date_str}"
    return await redis.get(key)


def _resolve_cuisine(ctx: dict, menu_date: date, override: str | None) -> list[str]:
    if override:
        remaining = [c for c in ctx["cuisine_prefs"] if c != override]
        return [override, *remaining, *[c for c in ALL_CUISINES if c not in [override, *remaining]]]

    if ctx["is_festival"] and ctx["festival_name"]:
        festival_cuisine = FESTIVAL_CUISINE_MAP.get(ctx["festival_name"])
        if festival_cuisine:
            remaining = [c for c in ctx["cuisine_prefs"] if c != festival_cuisine]
            return [festival_cuisine, *remaining, *[c for c in ALL_CUISINES if c not in [festival_cuisine, *remaining]]]

    base = list(ctx["cuisine_prefs"])
    return base + [c for c in ALL_CUISINES if c not in base]


async def _query_candidates(
    db: AsyncSession,
    slot: str,
    ctx: dict,
    excluded_ids: set,
    cuisine_pool: list[str],
) -> list[Recipe]:
    eating_mode = ctx["eating_mode"]
    is_nv_day = ctx["is_nv_day"]

    base_filters = [
        Recipe.meal_type == slot,
        Recipe.is_verified == True,  # noqa: E712
        Recipe.is_active == True,    # noqa: E712
    ]

    if excluded_ids:
        excluded_uuids = []
        for eid in excluded_ids:
            try:
                excluded_uuids.append(uuid.UUID(eid))
            except ValueError:
                pass
        if excluded_uuids:
            base_filters.append(Recipe.id.notin_(excluded_uuids))

    # Eating mode filter using PostgreSQL array contains
    if not is_nv_day:
        base_filters.append(
            or_(
                Recipe.eating_mode_tags.contains(["pure_veg"]),
                Recipe.eating_mode_tags.contains(["jain"]),
                Recipe.eating_mode_tags.contains(["sattvic"]),
            )
        )
    else:
        base_filters.append(Recipe.eating_mode_tags.contains([eating_mode]))

    for tag in ctx["health_tags"]:
        base_filters.append(Recipe.health_safe_tags.contains([tag]))

    for allergen in ctx["allergy_tags"]:
        base_filters.append(Recipe.allergy_free_tags.contains([f"{allergen}_free"]))

    results: list[Recipe] = []
    seen_ids: set = set()

    for cuisine in cuisine_pool[:3]:
        q = select(Recipe).where(and_(*base_filters, Recipe.cuisine_region == cuisine)).limit(20)
        rows = await db.execute(q)
        for r in rows.scalars().all():
            if str(r.id) not in seen_ids:
                results.append(r)
                seen_ids.add(str(r.id))
        if len(results) >= 5:
            break

    if len(results) < 3:
        q = select(Recipe).where(and_(*base_filters)).limit(20)
        rows = await db.execute(q)
        for r in rows.scalars().all():
            if str(r.id) not in seen_ids:
                results.append(r)
                seen_ids.add(str(r.id))

    return results


def _score_recipe(recipe: Recipe, target_cal: float) -> float:
    if target_cal <= 0:
        return 0.0
    cal_delta = abs(recipe.calories - target_cal) / target_cal
    protein_bonus = float(recipe.protein_g or 0) * 0.05
    return cal_delta - protein_bonus


def _select_by_macro(candidates: dict[str, list[Recipe]], ctx: dict) -> dict[str, Recipe | None]:
    calorie_target = ctx["macro_targets"]["calories"]
    selected: dict[str, Recipe | None] = {}
    for slot, recipes in candidates.items():
        if not recipes:
            selected[slot] = None
            continue
        target_cal = calorie_target * SLOT_RATIOS[slot]
        scored = sorted(recipes, key=lambda r: _score_recipe(r, target_cal))
        selected[slot] = scored[0]
    return selected


def _apply_variety_rules(
    selected: dict[str, Recipe | None],
    candidates: dict[str, list[Recipe]],
) -> dict[str, Recipe | None]:
    bf = selected.get("breakfast")
    lunch = selected.get("lunch")
    if bf and lunch and bf.main_ingredient and lunch.main_ingredient:
        if bf.main_ingredient == lunch.main_ingredient:
            alts = [r for r in candidates["lunch"] if r.main_ingredient != bf.main_ingredient]
            if alts:
                target_cal = 0
                selected["lunch"] = sorted(alts, key=lambda r: _score_recipe(r, target_cal))[0]

    ms = selected.get("morning_snack")
    es = selected.get("evening_snack")
    if ms and es and ms.id == es.id:
        alts = [r for r in candidates["evening_snack"] if r.id != ms.id]
        if alts:
            selected["evening_snack"] = alts[0]

    lunch2 = selected.get("lunch")
    dinner = selected.get("dinner")
    if lunch2 and dinner and lunch2.main_ingredient and dinner.main_ingredient:
        if lunch2.main_ingredient == dinner.main_ingredient:
            alts = [r for r in candidates["dinner"] if r.main_ingredient != lunch2.main_ingredient]
            if alts:
                selected["dinner"] = alts[0]

    return selected


async def _update_history(redis: Redis, owner_id: str, selected: dict[str, Recipe | None]) -> None:
    ts = time.time()
    for slot, recipe in selected.items():
        if recipe is None:
            continue
        key = f"menu_history:{owner_id}:{slot}"
        await redis.zadd(key, {str(recipe.id): ts})
        await redis.expire(key, 8 * 24 * 3600)


def _build_menu_record(
    selected: dict[str, Recipe | None],
    menu_date: date,
    owner_id: str,
    owner_type: str,
    cuisine_override: str | None,
) -> dict:
    total_calories = sum(r.calories for r in selected.values() if r)
    total_protein = sum(float(r.protein_g or 0) for r in selected.values() if r)
    total_carbs = sum(float(r.carbs_g or 0) for r in selected.values() if r)
    total_fat = sum(float(r.fat_g or 0) for r in selected.values() if r)

    return {
        "owner_id": uuid.UUID(owner_id),
        "owner_type": owner_type,
        "menu_date": menu_date,
        "breakfast_id": selected["breakfast"].id if selected.get("breakfast") else None,
        "morning_snack_id": selected["morning_snack"].id if selected.get("morning_snack") else None,
        "lunch_id": selected["lunch"].id if selected.get("lunch") else None,
        "evening_snack_id": selected["evening_snack"].id if selected.get("evening_snack") else None,
        "dinner_id": selected["dinner"].id if selected.get("dinner") else None,
        "total_calories": total_calories,
        "total_protein_g": round(total_protein, 2),
        "total_carbs_g": round(total_carbs, 2),
        "total_fat_g": round(total_fat, 2),
        "cuisine_override": cuisine_override,
        "is_regenerated": False,
        "wa_status": "pending",
    }
