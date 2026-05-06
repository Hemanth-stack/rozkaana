import logging
import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User
from app.models.user_nutrition_signal import UserNutritionSignal
from app.services.macro_scorer import calculate_targets

logger = logging.getLogger(__name__)

ANALYSIS_WINDOW_DAYS = 14

# Tags this service is allowed to auto-add (conservative — only clinically clear mappings).
# Tags like diabetes_t2, hypertension etc. require clinical diagnosis and must never be
# auto-added from symptoms alone.
VALID_AUTO_TAGS = {"anemia", "weight_loss"}


def detect_new_health_tags(signals: list, existing_tags: list[str]) -> list[str]:
    """
    Analyse a window of UserNutritionSignal rows and return health_tags to ADD.
    Never removes existing tags — only additive.
    """
    if not signals:
        return []

    n = len(signals)
    new_tags: list[str] = []

    # anemia: persistent hair loss + chronically low energy
    hair_loss_days = sum(1 for s in signals if s.hair_loss_noticed)
    low_energy_days = sum(1 for s in signals if s.energy_level and s.energy_level < 4)
    if hair_loss_days >= 3 and low_energy_days >= 5 and "anemia" not in existing_tags:
        new_tags.append("anemia")
        logger.info("Signal analysis: anemia detected — hair_loss=%d low_energy=%d over %d days",
                    hair_loss_days, low_energy_days, n)

    # weight_loss tag (triggers low-GI, higher-protein menu): repeated blood sugar crashes
    sugar_dip_days = sum(1 for s in signals if s.blood_sugar_dip)
    if sugar_dip_days >= 4 and "weight_loss" not in existing_tags and "diabetes_t2" not in existing_tags:
        new_tags.append("weight_loss")
        logger.info("Signal analysis: weight_loss tag added — blood_sugar_dips=%d over %d days",
                    sugar_dip_days, n)

    return new_tags


async def analyze_and_update_user(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """
    1. Fetch last ANALYSIS_WINDOW_DAYS of signals
    2. Detect new health_tags from symptom patterns
    3. If new tags found:
       a. Merge into user.health_tags (set union, no duplicates)
       b. Recalculate macro targets
       c. Flush to DB
       d. Queue tomorrow's menu generation
    Returns a summary dict.
    """
    cutoff = date.today() - timedelta(days=ANALYSIS_WINDOW_DAYS)
    result = await db.execute(
        select(UserNutritionSignal).where(
            UserNutritionSignal.user_id == user_id,
            UserNutritionSignal.signal_date >= cutoff,
        )
    )
    signals = result.scalars().all()

    if not signals:
        return {"user_id": str(user_id), "tags_added": [], "macro_recalculated": False, "menu_queued": False}

    user = await db.get(User, user_id)
    if not user:
        return {"user_id": str(user_id), "tags_added": [], "macro_recalculated": False, "menu_queued": False}

    existing_tags = list(user.health_tags or [])
    new_tags = detect_new_health_tags(signals, existing_tags)

    if not new_tags:
        return {"user_id": str(user_id), "tags_added": [], "macro_recalculated": False, "menu_queued": False}

    user.health_tags = list(set(existing_tags + new_tags))

    macro_recalculated = False
    if user.weight_kg and user.height_cm and user.age:
        targets = calculate_targets(user)
        user.daily_calorie_target = targets["daily_calorie_target"]
        user.daily_protein_target_g = targets["daily_protein_target_g"]
        user.daily_carbs_target_g = targets["daily_carbs_target_g"]
        user.daily_fat_target_g = targets["daily_fat_target_g"]
        macro_recalculated = True

    await db.flush()

    menu_queued = False
    try:
        from app.tasks.menu_tasks import generate_single_menu
        next_date = str(date.today() + timedelta(days=1))
        owner_id = str(user.household_id or user.id)
        owner_type = "household" if user.household_id else "user"
        generate_single_menu.delay(owner_id, owner_type, next_date, None)
        menu_queued = True
    except Exception as exc:
        logger.error("Failed to queue menu regen for user=%s after signal analysis: %s", user_id, exc)

    logger.info("Signal analysis complete user=%s tags_added=%s macro_recalculated=%s menu_queued=%s",
                user_id, new_tags, macro_recalculated, menu_queued)

    return {
        "user_id": str(user_id),
        "tags_added": new_tags,
        "macro_recalculated": macro_recalculated,
        "menu_queued": menu_queued,
    }
