from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.dependencies import get_current_user
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.user import (
    UpdateBasicRequest, UpdateEatingRequest, UpdateGoalRequest,
    UpdateHealthRequest, UpdateWhatsAppRequest, UserProfile,
)
from app.services.bmi_service import calculate_and_store_bmi
from app.services.macro_scorer import calculate_targets
from app.services.subscription_service import create_trial
from app.services.whatsapp_service import wa_service

router = APIRouter(prefix="/users", tags=["users"])


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

    calculate_and_store_bmi(current_user)
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
        targets = calculate_targets(current_user)
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
    await db.flush()

    sub = await create_trial(current_user.id, "solo_basic", db)

    if current_user.wa_phone and current_user.wa_opted_in:
        await wa_service.send_template(
            current_user.wa_phone,
            "rozkaana_trial_start",
            {"name": current_user.name, "trial_end": str(sub.trial_end)},
        )

    await db.refresh(current_user)
    return current_user
