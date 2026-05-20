import logging
import time
import uuid
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

from redis.asyncio import Redis
from sqlalchemy import and_, cast, or_, text
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy import String
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

# Adult-equivalent calorie weights by member type — used for grocery scaling
ADULT_EQUIV_WEIGHTS: dict[str, float] = {
    "adult":  1.0,
    "senior": 1.0,
    "teen":   0.9,
    "child":  0.75,
    "infant": 0.4,
}


def _child_weight(member) -> float:
    """Age-refined adult-equivalent weight for a HouseholdMember."""
    mt = getattr(member, "member_type", "adult")
    if mt == "infant":
        return 0.4
    if mt == "child":
        age = getattr(member, "age", None) or 0
        return 0.6 if age <= 7 else 0.75
    return ADULT_EQUIV_WEIGHTS.get(mt, 1.0)


# South Indian sub-regions map back to the legacy south_indian pool as a fallback.
# This lets existing south_indian-tagged recipes serve andhra/tamil/karnataka users
# until sub-regional recipe batches are fully generated.
_SOUTH_SUBREGION_PARENT: dict[str, str] = {
    "andhra":    "south_indian",
    "tamil":     "south_indian",
    "karnataka": "south_indian",
}

ALL_CUISINES = [
    "north_indian", "andhra", "tamil", "karnataka", "bengali", "gujarati",
    "maharashtrian", "punjabi", "hyderabadi", "rajasthani", "kerala", "goan",
    "sattvic",
    "south_indian",  # legacy — kept as fallback pool, not user-selectable
]

EATING_MODE_STRICTNESS = {
    "jain": 0,
    "sattvic": 1,
    "pure_veg": 2,
    "conditional_nv": 3,
    "full_nv": 4,
}

# Dinner style rotation for "mixed" preference (index = weekday, 0=Mon)
_DINNER_STYLE_ROTATION = [
    "rice_plate",  # Mon
    "tiffin",      # Tue
    "rice_plate",  # Wed
    "tiffin",      # Thu
    "rice_plate",  # Fri
    "roti_based",  # Sat
    "roti_based",  # Sun
]

# Universal South Indian base ingredients that appear across many dishes and
# should not count as "shared" when checking adjacent-meal ingredient overlap.
_EXEMPT_INGREDIENTS: set[str] = {
    "sambar", "rice", "coconut", "curry leaves", "mustard seeds",
    "urad dal", "chana dal", "tamarind", "curd", "yogurt",
    "ghee", "oil", "salt", "water", "green chilli", "ginger",
}


def _expand_cuisine(cuisine: str) -> list[str]:
    """Return cuisine + its legacy parent pool (for South Indian sub-regions)."""
    parent = _SOUTH_SUBREGION_PARENT.get(cuisine)
    return [cuisine, parent] if parent else [cuisine]


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
    selected = _apply_variety_rules(selected, candidates, calorie_target=ctx["macro_targets"]["calories"])

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
        dinner_style_pref = user.dinner_style_pref
        macro_targets = {
            "calories": calorie_target,
            "protein_g": float(user.daily_protein_target_g or calorie_target * 0.12 / 4),
            "carbs_g": float(user.daily_carbs_target_g or calorie_target * 0.60 / 4),
            "fat_g": float(user.daily_fat_target_g or calorie_target * 0.28 / 9),
        }
    else:
        from app.models.household_member import HouseholdMember
        household = await db.get(Household, uuid.UUID(owner_id))
        if not household:
            raise ValueError(f"Household {owner_id} not found")

        result = await db.execute(select(User).where(User.household_id == uuid.UUID(owner_id)))
        user_members = result.scalars().all()

        hm_result = await db.execute(
            select(HouseholdMember).where(HouseholdMember.household_id == uuid.UUID(owner_id))
        )
        hh_members = hm_result.scalars().all()

        if not user_members and not hh_members:
            raise ValueError(f"Household {owner_id} has no members")

        # Strictest eating mode across ALL members (registered users + head-managed profiles)
        all_eating_modes = (
            [m.eating_mode or "pure_veg" for m in user_members] +
            [m.eating_mode or "pure_veg" for m in hh_members]
        )
        eating_mode = min(all_eating_modes, key=lambda m: EATING_MODE_STRICTNESS.get(m, 99))

        health_tags = list(set(
            tag for m in (list(user_members) + list(hh_members))
            for tag in (m.health_tags or [])
        ))
        allergy_tags = list(set(
            tag for m in (list(user_members) + list(hh_members))
            for tag in (m.allergy_tags or [])
        ))
        cuisine_prefs = household.cuisine_prefs or ["north_indian"]
        head = next((m for m in user_members if m.is_household_head), user_members[0] if user_members else None)
        calorie_target = (head.daily_calorie_target if head else None) or 2000
        nv_days = []
        dinner_style_pref = head.dinner_style_pref if head else None

        # Adult-equivalent count for grocery ingredient scaling
        adult_equiv = float(len(user_members))
        adult_equiv += sum(_child_weight(m) for m in hh_members)
        member_count = max(1, round(adult_equiv))

        macro_targets = {
            "calories": calorie_target,
            "protein_g": float((head.daily_protein_target_g if head else None) or calorie_target * 0.12 / 4),
            "carbs_g": float((head.daily_carbs_target_g if head else None) or calorie_target * 0.60 / 4),
            "fat_g": float((head.daily_fat_target_g if head else None) or calorie_target * 0.28 / 9),
        }

    today_name = DAY_NAMES[menu_date.weekday()]
    if eating_mode == "full_nv":
        is_nv_day = True   # full_nv = non-veg every day; nv_days field is not relevant
    elif eating_mode == "conditional_nv":
        is_nv_day = today_name in [d.lower() for d in nv_days]
    else:
        is_nv_day = False  # pure_veg / jain / sattvic — never NV

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
        "dinner_style_pref": dinner_style_pref,
        "menu_date": menu_date,
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
    def _build_pool(primary: str | None) -> list[str]:
        pool: list[str] = []
        if primary:
            for c in _expand_cuisine(primary):
                if c not in pool:
                    pool.append(c)
        for pref in ctx["cuisine_prefs"]:
            for c in _expand_cuisine(pref):
                if c not in pool:
                    pool.append(c)
        for c in ALL_CUISINES:
            for e in _expand_cuisine(c):
                if e not in pool:
                    pool.append(e)
        return pool

    if override:
        return _build_pool(override)

    if ctx["is_festival"] and ctx["festival_name"]:
        festival_cuisine = FESTIVAL_CUISINE_MAP.get(ctx["festival_name"])
        if festival_cuisine:
            return _build_pool(festival_cuisine)

    return _build_pool(None)


async def _query_candidates(
    db: AsyncSession,
    slot: str,
    ctx: dict,
    excluded_ids: set,
    cuisine_pool: list[str],
) -> list[Recipe]:
    eating_mode = ctx["eating_mode"]
    is_nv_day = ctx["is_nv_day"]
    menu_date: date = ctx["menu_date"]
    dinner_style_pref: str | None = ctx.get("dinner_style_pref")

    def arr_contains(col, values: list[str]):
        return col.op("@>")(cast(values, PG_ARRAY(String)))

    core_filters = [
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
            core_filters.append(Recipe.id.notin_(excluded_uuids))

    # Eating mode filter respects the strictness hierarchy:
    # full_nv can eat anything; jain can only eat jain-tagged recipes.
    if eating_mode == "full_nv":
        # Least restrictive — can eat any recipe, no eating mode filter needed
        pass
    elif eating_mode == "conditional_nv" and is_nv_day:
        core_filters.append(or_(
            arr_contains(Recipe.eating_mode_tags, ["conditional_nv"]),
            arr_contains(Recipe.eating_mode_tags, ["pure_veg"]),
            arr_contains(Recipe.eating_mode_tags, ["sattvic"]),
            arr_contains(Recipe.eating_mode_tags, ["jain"]),
        ))
    elif eating_mode == "pure_veg" or (eating_mode == "conditional_nv" and not is_nv_day):
        core_filters.append(or_(
            arr_contains(Recipe.eating_mode_tags, ["pure_veg"]),
            arr_contains(Recipe.eating_mode_tags, ["sattvic"]),
            arr_contains(Recipe.eating_mode_tags, ["jain"]),
        ))
    elif eating_mode == "sattvic":
        core_filters.append(or_(
            arr_contains(Recipe.eating_mode_tags, ["sattvic"]),
            arr_contains(Recipe.eating_mode_tags, ["jain"]),
        ))
    else:
        # jain — most restrictive
        core_filters.append(arr_contains(Recipe.eating_mode_tags, ["jain"]))

    for tag in ctx["health_tags"]:
        core_filters.append(arr_contains(Recipe.health_safe_tags, [tag]))

    health_tags = ctx["health_tags"]
    if "hypertension" in health_tags:
        core_filters.append(or_(Recipe.sodium_mg.is_(None), Recipe.sodium_mg <= 600))
    if "diabetes_t2" in health_tags or "pcos" in health_tags:
        core_filters.append(or_(Recipe.glycemic_index.is_(None), Recipe.glycemic_index <= 55))
    if "kidney_disease" in health_tags:
        core_filters.append(or_(Recipe.potassium_mg.is_(None), Recipe.potassium_mg <= 400))

    # Dinner style filtering
    if slot == "dinner" and dinner_style_pref:
        if dinner_style_pref == "mixed":
            day_style = _DINNER_STYLE_ROTATION[menu_date.weekday()]
        else:
            day_style = dinner_style_pref
        core_filters.append(
            or_(
                Recipe.dish_category == day_style,
                Recipe.dish_category.is_(None),  # untagged recipes are still valid
            )
        )

    # Allergy filters kept separate so they can be relaxed when tag coverage is incomplete.
    allergy_filters = [
        arr_contains(Recipe.allergy_free_tags, [f"{allergen}_free"])
        for allergen in ctx["allergy_tags"]
    ]

    async def _run_query(filters: list) -> list[Recipe]:
        out: list[Recipe] = []
        seen: set = set()
        # First pass: user's top cuisines (preferred region + its fallback pool)
        for cuisine in cuisine_pool[:4]:
            q = select(Recipe).where(and_(*filters, Recipe.cuisine_region == cuisine)).limit(20)
            rows = await db.execute(q)
            for r in rows.scalars().all():
                if str(r.id) not in seen:
                    out.append(r)
                    seen.add(str(r.id))
            if len(out) >= 10:
                break
        # Second pass: expand to more of the cuisine pool — still cuisine-constrained
        # (prevents Kerala/North Indian dishes appearing for an Andhra user)
        if len(out) < 3:
            extended = cuisine_pool[4:10]
            if extended:
                q = select(Recipe).where(
                    and_(*filters, Recipe.cuisine_region.in_(extended))
                ).limit(20)
                rows = await db.execute(q)
                for r in rows.scalars().all():
                    if str(r.id) not in seen:
                        out.append(r)
                        seen.add(str(r.id))
        # Last resort: fully unconstrained — only when no cuisine-filtered results exist at all
        if len(out) == 0:
            logger.warning(
                "Cuisine pool exhausted for slot=%s — falling back to unconstrained query",
                slot,
            )
            q = select(Recipe).where(and_(*filters)).limit(20)
            rows = await db.execute(q)
            for r in rows.scalars().all():
                if str(r.id) not in seen:
                    out.append(r)
                    seen.add(str(r.id))
        return out

    results = await _run_query(core_filters + allergy_filters)

    # Fallback: allergy tag coverage is incomplete — missing tags should not starve the menu.
    if len(results) == 0 and allergy_filters:
        logger.warning(
            "Allergy filters returned 0 for slot=%s allergens=%s — retrying without allergy filter",
            slot, ctx["allergy_tags"],
        )
        results = await _run_query(core_filters)

    if len(results) == 0:
        logger.error(
            "ZERO candidates slot=%s eating_mode=%s health_tags=%s cuisine_pool=%s — slot will be None",
            slot, ctx["eating_mode"], ctx["health_tags"], cuisine_pool[:4],
        )
    elif len(results) < 3:
        logger.warning(
            "Low candidate pool slot=%s count=%d eating_mode=%s health_tags=%s",
            slot, len(results), ctx["eating_mode"], ctx["health_tags"],
        )

    return results


def _score_recipe(
    recipe: Recipe,
    target_cal: float,
    target_protein_g: float = 0,
    preferred_cuisines: list[str] | None = None,
) -> float:
    if target_cal <= 0:
        return 0.0
    cal_delta = abs(recipe.calories - target_cal) / target_cal
    if target_protein_g > 0:
        # 80% weight on calorie fit, 20% on protein fit
        protein_delta = abs(float(recipe.protein_g or 0) - target_protein_g) / max(target_protein_g, 1)
        score = cal_delta * 0.8 + protein_delta * 0.2
    else:
        score = cal_delta
    # Cuisine preference bonus: prefer the user's top cuisine even if calorically less perfect.
    # A bonus of 0.15 means an Andhra recipe 15% off in calories still beats a Kerala recipe
    # that's perfectly on-target, keeping regional authenticity for the primary cuisine.
    if preferred_cuisines and recipe.cuisine_region == preferred_cuisines[0]:
        score = max(0.0, score - 0.15)
    elif preferred_cuisines and len(preferred_cuisines) > 1 and recipe.cuisine_region == preferred_cuisines[1]:
        score = max(0.0, score - 0.07)
    return score


def _select_by_macro(candidates: dict[str, list[Recipe]], ctx: dict) -> dict[str, Recipe | None]:
    calorie_target = ctx["macro_targets"]["calories"]
    protein_target = ctx["macro_targets"]["protein_g"]
    preferred_cuisines = ctx.get("cuisine_prefs", [])
    top_cuisine = preferred_cuisines[0] if preferred_cuisines else None

    selected: dict[str, Recipe | None] = {}
    for slot, recipes in candidates.items():
        if not recipes:
            logger.error("No recipes available for slot=%s — DailyMenu will have a null slot", slot)
            selected[slot] = None
            continue
        slot_cal_target = calorie_target * SLOT_RATIOS[slot]
        slot_protein_target = protein_target * SLOT_RATIOS[slot]

        def score(r: Recipe) -> float:
            return _score_recipe(r, slot_cal_target, slot_protein_target, preferred_cuisines)

        # Prefer the user's exact top cuisine: if any candidates come from it, select only those.
        # south_indian is the *fallback pool* for andhra/tamil/karnataka — not an equal preference.
        # Only use the full mixed pool when the top cuisine has zero representation in this slot.
        top_cuisine_recipes = [r for r in recipes if r.cuisine_region == top_cuisine] if top_cuisine else []
        pool_to_score = top_cuisine_recipes if top_cuisine_recipes else recipes

        selected[slot] = sorted(pool_to_score, key=score)[0]
    return selected


def _get_ingredient_names(recipe: Recipe) -> set[str]:
    """All ingredient names from the recipe, excluding universal base ingredients."""
    names: set[str] = set()
    if recipe.main_ingredient:
        n = recipe.main_ingredient.lower().strip()
        if n and n not in _EXEMPT_INGREDIENTS:
            names.add(n)
    for ing in (recipe.ingredients or []):
        n = (ing.get("name") or "").lower().strip()
        if n and n not in _EXEMPT_INGREDIENTS:
            names.add(n)
    return names


def _ingredient_overlap(r1: Recipe, r2: Recipe) -> int:
    """Number of shared non-exempt ingredients between two recipes."""
    if not r1 or not r2:
        return 0
    return len(_get_ingredient_names(r1) & _get_ingredient_names(r2))


def _apply_variety_rules(
    selected: dict[str, Recipe | None],
    candidates: dict[str, list[Recipe]],
    calorie_target: float = 2000,
) -> dict[str, Recipe | None]:
    # 1. Breakfast and lunch should not share main ingredient
    bf = selected.get("breakfast")
    lunch = selected.get("lunch")
    if bf and lunch and bf.main_ingredient and lunch.main_ingredient:
        if bf.main_ingredient == lunch.main_ingredient:
            alts = [r for r in candidates["lunch"] if r.main_ingredient != bf.main_ingredient]
            if alts:
                lunch_target = calorie_target * SLOT_RATIOS["lunch"]
                selected["lunch"] = sorted(alts, key=lambda r: _score_recipe(r, lunch_target))[0]

    # 2. Lunch and dinner should not share main ingredient
    lunch2 = selected.get("lunch")
    dinner = selected.get("dinner")
    if lunch2 and dinner and lunch2.main_ingredient and dinner.main_ingredient:
        if lunch2.main_ingredient == dinner.main_ingredient:
            alts = [r for r in candidates["dinner"] if r.main_ingredient != lunch2.main_ingredient]
            if alts:
                selected["dinner"] = alts[0]

    # 3. Snacks should not be identical to each other
    ms = selected.get("morning_snack")
    es = selected.get("evening_snack")
    if ms and es and ms.id == es.id:
        alts = [r for r in candidates["evening_snack"] if r.id != ms.id]
        if alts:
            selected["evening_snack"] = alts[0]

    # 4. Avoid high ingredient overlap between adjacent meals (exempt common South Indian bases)
    pairs = [("breakfast", "morning_snack"), ("morning_snack", "lunch"),
             ("lunch", "evening_snack"), ("evening_snack", "dinner")]
    for slot_a, slot_b in pairs:
        ra, rb = selected.get(slot_a), selected.get(slot_b)
        if ra and rb and _ingredient_overlap(ra, rb) >= 4:
            alts = [
                r for r in candidates.get(slot_b, [])
                if r.id != rb.id and _ingredient_overlap(ra, r) < 4
            ]
            if alts:
                selected[slot_b] = alts[0]

    # 5. Breakfast and dinner must not be the exact same dish (tiffin overlap prevention)
    bf = selected.get("breakfast")
    dinner = selected.get("dinner")
    if bf and dinner and bf.name == dinner.name:
        alts = [r for r in candidates["dinner"] if r.name != bf.name]
        if alts:
            dinner_target = calorie_target * SLOT_RATIOS["dinner"]
            selected["dinner"] = sorted(alts, key=lambda r: _score_recipe(r, dinner_target))[0]

    return selected


async def _update_history(redis: Redis, owner_id: str, selected: dict[str, Recipe | None]) -> None:
    ts = time.time()
    for slot, recipe in selected.items():
        if recipe is None:
            continue
        key = f"menu_history:{owner_id}:{slot}"
        await redis.zadd(key, {str(recipe.id): ts})
        await redis.expire(key, 8 * 24 * 3600)


async def get_menu_insights(
    db: AsyncSession,
    redis: Redis,
    owner_id: str,
    owner_type: str,
    menu_date: date,
) -> dict:
    """Return diagnostic info about how the menu engine would build today's menu."""
    ctx = await _load_context(db, owner_id, owner_type, menu_date)
    excluded = await _get_excluded_ids(redis, owner_id)
    cuisine_pool = _resolve_cuisine(ctx, menu_date, None)

    candidate_counts: dict[str, int] = {}
    for slot in SLOT_RATIOS:
        candidates = await _query_candidates(
            db, slot, ctx, excluded.get(slot, set()), cuisine_pool
        )
        candidate_counts[slot] = len(candidates)

    cuisine_used = cuisine_pool[0] if cuisine_pool else "unknown"
    if ctx.get("is_festival") and ctx.get("festival_name"):
        cuisine_reason = f"Festival: {ctx['festival_name']}"
    else:
        prefs = ctx.get("cuisine_prefs") or []
        cuisine_reason = f"Preference: {prefs[0]}" if prefs else "Default rotation"

    return {
        "signals_active": {
            "eating_mode": ctx.get("eating_mode"),
            "health_tags": ctx.get("health_tags", []),
            "allergy_tags": ctx.get("allergy_tags", []),
            "calorie_target": ctx.get("calorie_target"),
            "is_festival": ctx.get("is_festival", False),
            "festival_name": ctx.get("festival_name"),
            "is_nv_day": ctx.get("is_nv_day", False),
            "dinner_style_pref": ctx.get("dinner_style_pref"),
        },
        "candidate_pool": candidate_counts,
        "cuisine_used": cuisine_used,
        "cuisine_reason": cuisine_reason,
        "calorie_target": ctx.get("calorie_target"),
        "exclusion_window_7d": {slot: len(ids) for slot, ids in excluded.items()},
    }


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
        # is_regenerated and delivery-tracking fields (wa_status, email_status, etc.) are
        # intentionally excluded here so they are NOT overwritten when a menu is regenerated.
        # generate_single_menu sets is_regenerated explicitly after this call.
    }
