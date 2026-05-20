import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.dependencies import get_current_user
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.user import (
    NutritionSignalRequest, NutritionSignalResponse,
    UpdateBasicRequest, UpdateEatingRequest, UpdateGoalRequest,
    UpdateHealthRequest, UpdateWhatsAppRequest, UserProfile,
)
from app.services.bmi_service import calculate_and_store_bmi
from app.services.macro_scorer import calculate_targets
from app.services.subscription_service import create_trial

router = APIRouter(prefix="/users", tags=["users"])


@router.delete("/me", status_code=204)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.is_active = False
    await db.flush()
    # Cancel any active subscription
    result = await db.execute(select(Subscription).where(Subscription.user_id == current_user.id))
    sub = result.scalar_one_or_none()
    if sub and sub.status in ("trial", "active"):
        sub.status = "cancelled"
        await db.flush()


@router.get("/me", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me/basic", response_model=UserProfile)
async def update_basic(
    request: UpdateBasicRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request.name is not None:
        current_user.name = request.name
    if request.age is not None:
        current_user.age = request.age
    if request.gender is not None:
        current_user.gender = request.gender
    if request.weight_kg is not None:
        current_user.weight_kg = request.weight_kg
    if request.height_cm is not None:
        current_user.height_cm = request.height_cm
    if request.activity_level is not None:
        current_user.activity_level = request.activity_level

    calculate_and_store_bmi(current_user)
    if current_user.weight_kg and current_user.height_cm and current_user.age:
        cuisine_pref = (current_user.cuisine_prefs or [None])[0]
        targets = calculate_targets(current_user, cuisine_pref=cuisine_pref)
        current_user.daily_calorie_target = targets["daily_calorie_target"]
        current_user.daily_protein_target_g = targets["daily_protein_target_g"]
        current_user.daily_carbs_target_g = targets["daily_carbs_target_g"]
        current_user.daily_fat_target_g = targets["daily_fat_target_g"]
    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.put("/me/health", response_model=UserProfile)
async def update_health(
    request: UpdateHealthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request.health_tags is not None:
        current_user.health_tags = request.health_tags
    if request.allergy_tags is not None:
        current_user.allergy_tags = request.allergy_tags
    if current_user.weight_kg and current_user.height_cm and current_user.age:
        cuisine_pref = (current_user.cuisine_prefs or [None])[0]
        targets = calculate_targets(current_user, cuisine_pref=cuisine_pref)
        current_user.daily_calorie_target = targets["daily_calorie_target"]
        current_user.daily_protein_target_g = targets["daily_protein_target_g"]
        current_user.daily_carbs_target_g = targets["daily_carbs_target_g"]
        current_user.daily_fat_target_g = targets["daily_fat_target_g"]
    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.put("/me/eating", response_model=UserProfile)
async def update_eating(
    request: UpdateEatingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request.eating_mode is not None:
        current_user.eating_mode = request.eating_mode
    if request.nv_days is not None:
        current_user.nv_days = request.nv_days
    if request.cuisine_prefs is not None:
        current_user.cuisine_prefs = request.cuisine_prefs
        # Recalculate macros when cuisine changes — split ratios are cuisine-aware
        if current_user.weight_kg and current_user.height_cm and current_user.age:
            cuisine_pref = request.cuisine_prefs[0] if request.cuisine_prefs else None
            targets = calculate_targets(current_user, cuisine_pref=cuisine_pref)
            current_user.daily_calorie_target = targets["daily_calorie_target"]
            current_user.daily_protein_target_g = targets["daily_protein_target_g"]
            current_user.daily_carbs_target_g = targets["daily_carbs_target_g"]
            current_user.daily_fat_target_g = targets["daily_fat_target_g"]
    if request.dinner_style_pref is not None:
        current_user.dinner_style_pref = request.dinner_style_pref

    if current_user.is_household_head and current_user.household_id:
        from app.models.household import Household
        from app.services.menu_engine import EATING_MODE_STRICTNESS
        household = await db.get(Household, current_user.household_id)
        if household:
            result = await db.execute(
                select(User).where(User.household_id == current_user.household_id)
            )
            members = result.scalars().all()
            modes = [m.eating_mode or "pure_veg" for m in members]
            household.shared_eating_mode = min(modes, key=lambda m: EATING_MODE_STRICTNESS.get(m, 99))

    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.put("/me/goal", response_model=UserProfile)
async def update_goal(
    request: UpdateGoalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid_goals = {"weight_loss", "maintenance", "muscle_gain"}
    if request.goal not in valid_goals:
        raise HTTPException(status_code=400, detail=f"goal must be one of: {valid_goals}")
    current_user.goal = request.goal
    if current_user.weight_kg and current_user.height_cm and current_user.age:
        cuisine_pref = (current_user.cuisine_prefs or [None])[0]
        targets = calculate_targets(current_user, cuisine_pref=cuisine_pref)
        current_user.daily_calorie_target = targets["daily_calorie_target"]
        current_user.daily_protein_target_g = targets["daily_protein_target_g"]
        current_user.daily_carbs_target_g = targets["daily_carbs_target_g"]
        current_user.daily_fat_target_g = targets["daily_fat_target_g"]
    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.put("/me/whatsapp", response_model=UserProfile)
async def update_whatsapp(
    request: UpdateWhatsAppRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.wa_phone = request.wa_phone
    success = await wa_service.opt_in_contact(request.wa_phone, current_user.name or "User")
    current_user.wa_opted_in = success
    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.post("/me/onboarding-complete", response_model=UserProfile)
async def complete_onboarding(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    missing = []
    if not current_user.name:
        missing.append("name")
    if not current_user.age:
        missing.append("age")
    if not current_user.gender:
        missing.append("gender")
    if not current_user.weight_kg:
        missing.append("weight_kg")
    if not current_user.height_cm:
        missing.append("height_cm")
    if not current_user.eating_mode:
        missing.append("eating_mode")
    if not current_user.cuisine_prefs:
        missing.append("cuisine_prefs")

    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Complete your profile first. Missing: {', '.join(missing)}",
        )

    current_user.onboarding_complete = True

    if current_user.weight_kg and current_user.height_cm and current_user.age:
        cuisine_pref = (current_user.cuisine_prefs or [None])[0]
        targets = calculate_targets(current_user, cuisine_pref=cuisine_pref)
        current_user.daily_calorie_target = targets["daily_calorie_target"]
        current_user.daily_protein_target_g = targets["daily_protein_target_g"]
        current_user.daily_carbs_target_g = targets["daily_carbs_target_g"]
        current_user.daily_fat_target_g = targets["daily_fat_target_g"]

    await db.flush()

    sub = await create_trial(current_user.id, "solo_basic", db)

    # Commit the DB changes (onboarding_complete + macro targets + subscription) BEFORE
    # any side effects. An email or task-queue failure must never roll back the DB commit.
    await db.commit()
    await db.refresh(current_user)

    if current_user.email and current_user.email_verified:
        try:
            from app.services.email_service import email_service
            await email_service.send_trial_start(
                current_user.email,
                current_user.name or "there",
                str(sub.trial_end),
            )
        except Exception:
            logger.exception(
                "Failed to send trial-start email to %s — onboarding still complete",
                current_user.email,
            )

    try:
        from datetime import timedelta
        from app.tasks.menu_tasks import generate_single_menu
        next_date = str(date.today() + timedelta(days=1))
        owner_id = str(current_user.household_id or current_user.id)
        owner_type = "household" if current_user.household_id else "user"
        generate_single_menu.delay(owner_id, owner_type, next_date, None)
    except Exception:
        logger.exception("Failed to queue first menu for user %s", current_user.id)

    return current_user


# ── NUTRITION SIGNALS ──────────────────────────────────────────────────────────

@router.post("/me/signals", response_model=NutritionSignalResponse, status_code=201)
async def log_nutrition_signal(
    request: NutritionSignalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log today's nutrition signals (energy, sleep, digestion, biometrics). Upserts by date."""
    from app.models.user_nutrition_signal import UserNutritionSignal
    today = date.today()

    result = await db.execute(
        select(UserNutritionSignal).where(
            UserNutritionSignal.user_id == current_user.id,
            UserNutritionSignal.signal_date == today,
        )
    )
    signal = result.scalar_one_or_none()
    data = request.model_dump(exclude_none=True)

    if signal:
        for k, v in data.items():
            setattr(signal, k, v)
    else:
        signal = UserNutritionSignal(user_id=current_user.id, signal_date=today, **data)
        db.add(signal)

    await db.flush()
    await db.refresh(signal)
    return signal


@router.get("/me/signals", response_model=list[NutritionSignalResponse])
async def get_nutrition_signals(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent nutrition signals (1-30 days)."""
    from app.models.user_nutrition_signal import UserNutritionSignal
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=min(days, 30))
    result = await db.execute(
        select(UserNutritionSignal).where(
            UserNutritionSignal.user_id == current_user.id,
            UserNutritionSignal.signal_date >= cutoff,
        ).order_by(UserNutritionSignal.signal_date.desc())
    )
    return result.scalars().all()


@router.get("/me/signals/deficiency-hints")
async def get_deficiency_hints(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detect nutritional deficiency patterns from 30 days of logged signals."""
    from app.models.user_nutrition_signal import UserNutritionSignal
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=30)
    result = await db.execute(
        select(UserNutritionSignal).where(
            UserNutritionSignal.user_id == current_user.id,
            UserNutritionSignal.signal_date >= cutoff,
        )
    )
    signals = result.scalars().all()
    if not signals:
        return {"hints": [], "days_of_data": 0, "analysis_period_days": 30}

    n = len(signals)
    hints = []

    hair_loss = sum(1 for s in signals if s.hair_loss_noticed)
    if hair_loss >= max(3, n * 0.2):
        hints.append({
            "symptom": "hair_loss",
            "likely_deficiencies": ["iron", "zinc", "selenium", "protein"],
            "foods": ["pumpkin seeds", "eggs", "spinach", "lentils"],
            "severity": "high" if hair_loss >= n * 0.5 else "moderate",
        })

    cramps = sum(1 for s in signals if s.muscle_cramps)
    if cramps >= max(2, n * 0.15):
        hints.append({
            "symptom": "muscle_cramps",
            "likely_deficiencies": ["magnesium", "potassium", "calcium"],
            "foods": ["bananas", "spinach", "almonds", "sweet potato"],
            "severity": "moderate",
        })

    low_energy = sum(1 for s in signals if s.energy_level and s.energy_level < 4)
    if low_energy >= max(5, n * 0.3):
        hints.append({
            "symptom": "persistent_low_energy",
            "likely_deficiencies": ["iron", "vitamin_b12", "folate", "vitamin_d"],
            "foods": ["fortified milk", "leafy greens", "legumes", "eggs"],
            "severity": "high",
            "action": "Consider blood test: B12, iron, vitamin D",
        })

    sugar_dips = sum(1 for s in signals if s.blood_sugar_dip)
    if sugar_dips >= max(3, n * 0.2):
        hints.append({
            "symptom": "blood_sugar_crashes",
            "likely_cause": "High-GI meals or insufficient protein",
            "recommendations": ["Protein at every meal", "Avoid refined carbs", "Eat every 3-4h"],
            "severity": "moderate",
        })

    poor_sleep = sum(1 for s in signals if s.sleep_quality and s.sleep_quality < 4)
    if poor_sleep >= max(5, n * 0.3):
        hints.append({
            "symptom": "poor_sleep",
            "likely_causes": ["magnesium deficiency", "high carbs at night"],
            "foods": ["pumpkin seeds", "banana", "warm milk"],
            "recommendations": ["No heavy meals 3h before bed", "Increase magnesium-rich foods"],
            "severity": "moderate",
        })

    return {"hints": hints, "days_of_data": n, "analysis_period_days": 30}
