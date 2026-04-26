from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from redis import Redis
from datetime import date
from typing import Dict, List
import uuid
from app.models.recipe import Recipe
from app.models.user import User
from app.models.household import Household
from app.utils.festival_calendar import is_festival
from app.config import settings

SLOT_RATIOS = {
    "breakfast": 0.25, "morning_snack": 0.10,
    "lunch": 0.35, "evening_snack": 0.10, "dinner": 0.20
}
FLEX_BAND = 0.10

FESTIVAL_CUISINE_MAP = {
    "Diwali": "north_indian",
    "Eid": "hyderabadi",
    # Add more
}

async def generate_menu(
    db: AsyncSession,
    redis: Redis,
    owner_id: str,
    owner_type: str,
    menu_date: date,
    cuisine_override: str = None
) -> Dict:
    # 1. Load context
    ctx = await _load_context(db, owner_id, owner_type, menu_date)

    # 2. Fetch excluded recipe IDs from Redis (last 7 days per slot)
    excluded = await _get_excluded_ids(redis, owner_id)

    # 3. Determine cuisine pool for today
    cuisine_pool = _resolve_cuisine(
        ctx["cuisine_prefs"], menu_date, ctx["is_festival"],
        override=cuisine_override
    )

    # 4. For each slot, query candidate recipes
    slots = ["breakfast", "morning_snack", "lunch", "evening_snack", "dinner"]
    candidates = {}
    for slot in slots:
        candidates[slot] = await _query_candidates(
            db, slot, ctx, excluded[slot], cuisine_pool
        )

    # 5. Score & select best combo per slot
    selected = _select_by_macro(candidates, ctx["macro_targets"])

    # 6. Variety pass — ensure no same main_ingredient on same day
    selected = _apply_variety_rules(selected, candidates)

    # 7. Write to Redis history & return
    await _update_history(redis, owner_id, selected)
    return _build_menu_record(selected, menu_date, owner_id, owner_type)

async def _load_context(db: AsyncSession, owner_id: str, owner_type: str, menu_date: date) -> Dict:
    if owner_type == "user":
        user = await db.get(User, owner_id)
        eating_mode = user.eating_mode
        health_tags = user.health_tags or []
        allergy_tags = user.allergy_tags or []
        cuisine_prefs = user.cuisine_prefs or []
        calorie_target = user.daily_calorie_target or 2000
        nv_days = user.nv_days or []
        is_nv_day = menu_date.weekday() in [nv_days.index(d) if d in ["monday", "tuesday", ...] else -1]  # map to int
    else:
        household = await db.get(Household, owner_id)
        # Aggregate from members
        members = await db.execute(select(User).where(User.household_id == owner_id))
        members = members.scalars().all()
        eating_mode = household.shared_eating_mode
        health_tags = list(set(sum([m.health_tags or [] for m in members], [])))
        allergy_tags = list(set(sum([m.allergy_tags or [] for m in members], [])))
        cuisine_prefs = household.cuisine_prefs or []
        calorie_target = sum([m.daily_calorie_target or 2000 for m in members]) / len(members)
        nv_days = []  # household level?
        is_nv_day = False

    is_festival = is_festival(menu_date)
    macro_targets = {
        "calories": calorie_target,
        "protein": calorie_target * 0.15 / 4  # rough
    }
    return {
        "eating_mode": eating_mode,
        "health_tags": health_tags,
        "allergy_tags": allergy_tags,
        "cuisine_prefs": cuisine_prefs,
        "calorie_target": calorie_target,
        "macro_targets": macro_targets,
        "is_nv_day": is_nv_day,
        "is_festival": is_festival,
        "festival_name": None  # if is_festival
    }

async def _get_excluded_ids(redis: Redis, owner_id: str) -> Dict[str, set]:
    excluded = {}
    slots = ["breakfast", "morning_snack", "lunch", "evening_snack", "dinner"]
    for slot in slots:
        key = f"menu_history:{owner_id}:{slot}"
        # ZRANGE with score > now - 7 days
        # For simplicity, get all and filter
        ids = redis.zrange(key, 0, -1)
        excluded[slot] = set(ids)
    return excluded

def _resolve_cuisine(prefs: List[str], menu_date: date, is_festival: bool, override: str = None) -> List[str]:
    if override:
        return [override, *prefs]

    if is_festival:
        # Assume festival_name from context
        festival_cuisine = FESTIVAL_CUISINE_MAP.get("festival_name", None)
        if festival_cuisine:
            return [festival_cuisine, *prefs]

    if menu_date.weekday() == 5:  # Saturday
        all_indian = ["north_indian", "south_indian", "bengali", "gujarati", "hyderabadi", "marathi"]
        expanded = [*prefs, *[c for c in all_indian if c not in prefs]]
        return expanded

    return prefs

async def _query_candidates(db: AsyncSession, slot: str, ctx: Dict, excluded_ids: set, cuisine_pool: List[str]) -> List[Recipe]:
    from sqlalchemy import and_, or_, not_
    query = (
        select(Recipe)
        .where(Recipe.meal_type == slot)
        .where(Recipe.is_verified == True)
        .where(Recipe.is_active == True)
        .where(Recipe.id.notin_(excluded_ids))
        .where(Recipe.eating_mode_tags.contains([ctx["eating_mode"]]))
    )

    if not ctx["is_nv_day"]:
        query = query.where(or_(
            Recipe.eating_mode_tags.contains(["pure_veg"]),
            Recipe.eating_mode_tags.contains(["jain"]),
            Recipe.eating_mode_tags.contains(["sattvic"])
        ))

    for tag in ctx["health_tags"]:
        query = query.where(Recipe.health_safe_tags.contains([tag]))

    for allergen in ctx["allergy_tags"]:
        query = query.where(Recipe.allergy_free_tags.contains([f"{allergen}_free"]))

    results = []
    for cuisine in cuisine_pool:
        tier_results = await db.execute(
            query.where(Recipe.cuisine_region == cuisine).limit(20)
        )
        results.extend(tier_results.scalars().all())
        if len(results) >= 5:
            break

    if len(results) < 3:
        fallback = await db.execute(query.limit(10))
        results.extend(fallback.scalars().all())

    return results

def _score_recipe(recipe: Recipe, target_cal: int) -> float:
    cal_delta = abs(recipe.calories - target_cal) / target_cal
    cal_penalty = max(0, cal_delta - FLEX_BAND) * 10
    protein_score = -recipe.protein_g * 0.1
    return cal_penalty + protein_score

def _select_by_macro(candidates: Dict[str, List[Recipe]], macro_targets: Dict) -> Dict[str, Recipe]:
    selected = {}
    for slot, recipes in candidates.items():
        if not recipes:
            continue
        target_cal = macro_targets["calories"] * SLOT_RATIOS[slot]
        scored = sorted(recipes, key=lambda r: _score_recipe(r, target_cal))
        selected[slot] = scored[0]
    return selected

def _apply_variety_rules(selected: Dict[str, Recipe], candidates: Dict[str, List[Recipe]]) -> Dict[str, Recipe]:
    # Rule 1: breakfast & lunch must not share main_ingredient
    if selected.get("breakfast") and selected.get("lunch"):
        if selected["breakfast"].main_ingredient == selected["lunch"].main_ingredient:
            alternates = [r for r in candidates["lunch"]
                          if r.main_ingredient != selected["breakfast"].main_ingredient
                          and r.id != selected["breakfast"].id]
            if alternates:
                selected["lunch"] = alternates[0]

    # Rule 2: no same recipe in snack slots
    if selected.get("morning_snack") and selected.get("evening_snack"):
        if selected["morning_snack"].id == selected["evening_snack"].id:
            evn_alts = [r for r in candidates["evening_snack"]
                        if r.id != selected["morning_snack"].id]
            if evn_alts:
                selected["evening_snack"] = evn_alts[0]

    # Rule 3: texture variety — placeholder
    return selected

async def _update_history(redis: Redis, owner_id: str, selected: Dict[str, Recipe]):
    import time
    ts = int(time.time())
    for slot, recipe in selected.items():
        key = f"menu_history:{owner_id}:{slot}"
        redis.zadd(key, {str(recipe.id): ts})
        redis.expire(key, 8 * 24 * 3600)  # 8 days

def _build_menu_record(selected: Dict[str, Recipe], menu_date: date, owner_id: str, owner_type: str) -> Dict:
    total_calories = sum([r.calories for r in selected.values() if r])
    total_protein = sum([r.protein_g for r in selected.values() if r])
    return {
        "id": str(uuid.uuid4()),
        "owner_id": owner_id,
        "owner_type": owner_type,
        "menu_date": menu_date,
        "breakfast_id": selected.get("breakfast").id if selected.get("breakfast") else None,
        "morning_snack_id": selected.get("morning_snack").id if selected.get("morning_snack") else None,
        "lunch_id": selected.get("lunch").id if selected.get("lunch") else None,
        "evening_snack_id": selected.get("evening_snack").id if selected.get("evening_snack") else None,
        "dinner_id": selected.get("dinner").id if selected.get("dinner") else None,
        "total_calories": total_calories,
        "total_protein_g": total_protein,
        "cuisine_override": None,
        "is_regenerated": False,
        "pdf_key": None,
        "pdf_url": None,
        "wa_sent_at": None,
        "wa_status": "pending",
        "generated_at": None
    }