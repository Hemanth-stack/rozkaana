import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.household import Household
from app.models.household_member import HouseholdMember
from app.models.household_member_signal import HouseholdMemberSignal
from app.models.user import User
from app.schemas.household import (
    HouseholdCreate, HouseholdResponse, InviteResponse, UpdatePreferencesRequest,
)
from app.schemas.household_member import (
    HouseholdMemberCreate, HouseholdMemberUpdate, HouseholdMemberResponse,
    MemberSignalCreate, MemberSignalResponse,
)
from app.services.bmi_service import calculate_and_store_bmi
from app.services.macro_scorer import calculate_targets
from app.services.menu_engine import EATING_MODE_STRICTNESS
from app.utils.redis_client import get_redis, invite_token_key

router = APIRouter(prefix="/household", tags=["household"])


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _require_head(current_user: User) -> None:
    if not current_user.is_household_head:
        raise HTTPException(status_code=403, detail="Only household head can manage members")
    if not current_user.household_id:
        raise HTTPException(status_code=400, detail="Not in a household")


async def _recompute_eating_mode(household: Household, db: AsyncSession) -> None:
    """Recalculate household.shared_eating_mode from ALL members (users + HouseholdMembers)."""
    user_result = await db.execute(select(User).where(User.household_id == household.id))
    hm_result   = await db.execute(select(HouseholdMember).where(HouseholdMember.household_id == household.id))
    all_modes = (
        [m.eating_mode or "pure_veg" for m in user_result.scalars().all()] +
        [m.eating_mode or "pure_veg" for m in hm_result.scalars().all()]
    )
    if all_modes:
        household.shared_eating_mode = min(all_modes, key=lambda m: EATING_MODE_STRICTNESS.get(m, 99))


async def _recount_members(household: Household, db: AsyncSession) -> None:
    """Refresh adult_count and child_count from HouseholdMember rows."""
    result = await db.execute(
        select(HouseholdMember).where(HouseholdMember.household_id == household.id)
    )
    members = result.scalars().all()
    adult_types = {"adult", "senior", "teen"}
    household.adult_count = sum(1 for m in members if m.member_type in adult_types)
    household.child_count = sum(1 for m in members if m.member_type not in adult_types)


async def _build_household_response(household: Household, db: AsyncSession) -> dict:
    user_result = await db.execute(select(User).where(User.household_id == household.id))
    hm_result   = await db.execute(select(HouseholdMember).where(HouseholdMember.household_id == household.id))
    members    = user_result.scalars().all()
    hh_members = hm_result.scalars().all()

    hh_member_responses = [HouseholdMemberResponse.from_orm_with_flags(m) for m in hh_members]

    return {
        "id": household.id,
        "name": household.name,
        "head_user_id": household.head_user_id,
        "shared_eating_mode": household.shared_eating_mode,
        "member_count": household.member_count,
        "adult_count": household.adult_count or 0,
        "child_count": household.child_count or 0,
        "cuisine_prefs": household.cuisine_prefs or [],
        "members": members,
        "household_members": hh_member_responses,
    }


# ── Registered-user household management (existing) ──────────────────────────

@router.post("/", response_model=HouseholdResponse, status_code=201)
async def create_household(
    request: HouseholdCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.household_id:
        raise HTTPException(status_code=400, detail="Already in a household")

    household = Household(
        name=request.name,
        head_user_id=current_user.id,
        shared_eating_mode=current_user.eating_mode or "pure_veg",
        member_count=1,
        adult_count=0,
        child_count=0,
        cuisine_prefs=request.cuisine_prefs or current_user.cuisine_prefs or [],
    )
    db.add(household)
    await db.flush()
    await db.refresh(household)

    current_user.household_id = household.id
    current_user.is_household_head = True
    await db.flush()

    return await _build_household_response(household, db)


@router.get("/", response_model=HouseholdResponse)
async def get_household(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.household_id:
        raise HTTPException(status_code=404, detail="Not in a household")
    household = await db.get(Household, current_user.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    return await _build_household_response(household, db)


@router.post("/invite", response_model=InviteResponse)
async def invite_member(
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.household_id:
        raise HTTPException(status_code=400, detail="Not in a household")
    if not current_user.is_household_head:
        raise HTTPException(status_code=403, detail="Only household head can invite")

    token = str(uuid.uuid4())
    key = invite_token_key(token)
    await redis.set(key, str(current_user.household_id), ex=48 * 3600)

    invite_url = f"{settings.FRONTEND_URL}/join/{token}"
    return InviteResponse(invite_url=invite_url, token=token)


@router.post("/join/{token}", response_model=HouseholdResponse)
async def join_household(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    if current_user.household_id:
        raise HTTPException(status_code=400, detail="Already in a household")

    key = invite_token_key(token)
    household_id_str = await redis.get(key)
    if not household_id_str:
        raise HTTPException(status_code=404, detail="Invite token invalid or expired")

    household = await db.get(Household, uuid.UUID(household_id_str))
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    if (household.member_count or 0) >= 6:
        raise HTTPException(status_code=400, detail="Household is full (max 6 registered members)")

    current_user.household_id = household.id
    household.member_count = (household.member_count or 0) + 1

    await _recompute_eating_mode(household, db)
    await redis.delete(key)
    await db.flush()

    return await _build_household_response(household, db)


@router.delete("/member/{user_id}", status_code=204)
async def remove_member(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_household_head:
        raise HTTPException(status_code=403, detail="Only household head can remove members")

    try:
        target_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    if target_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself as head")

    result = await db.execute(select(User).where(User.id == target_id))
    target = result.scalar_one_or_none()
    if not target or target.household_id != current_user.household_id:
        raise HTTPException(status_code=404, detail="User not in your household")

    household = await db.get(Household, current_user.household_id)
    target.household_id = None
    if household:
        household.member_count = max(1, (household.member_count or 1) - 1)
        await _recompute_eating_mode(household, db)

    await db.flush()


@router.post("/leave", status_code=204)
async def leave_household(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.household_id:
        raise HTTPException(status_code=400, detail="Not in a household")
    if current_user.is_household_head:
        raise HTTPException(status_code=400,
                            detail="Head cannot leave — transfer ownership or delete the household")

    household = await db.get(Household, current_user.household_id)
    current_user.household_id = None
    if household:
        household.member_count = max(1, (household.member_count or 1) - 1)
    await db.flush()


@router.put("/preferences", response_model=HouseholdResponse)
async def update_preferences(
    request: UpdatePreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_household_head:
        raise HTTPException(status_code=403, detail="Only household head can update preferences")
    if not current_user.household_id:
        raise HTTPException(status_code=400, detail="Not in a household")

    household = await db.get(Household, current_user.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    household.cuisine_prefs = request.cuisine_prefs
    await db.flush()
    return await _build_household_response(household, db)


# ── HouseholdMember CRUD (head-managed profiles for children and unregistered adults) ──

@router.post("/members", response_model=HouseholdMemberResponse, status_code=201)
async def add_household_member(
    request: HouseholdMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a family member profile (child, elderly parent, etc.) managed by the head."""
    await _require_head(current_user)

    member = HouseholdMember(
        household_id=current_user.household_id,
        name=request.name,
        member_type=request.member_type,
        age=request.age,
        gender=request.gender,
        weight_kg=request.weight_kg,
        height_cm=request.height_cm,
        eating_mode=request.eating_mode,
        activity_level=request.activity_level,
        health_tags=request.health_tags or [],
        allergy_tags=request.allergy_tags or [],
        goal=request.goal,
    )

    # Calculate BMI and macro targets using the same logic as User profiles
    calculate_and_store_bmi(member)

    db.add(member)
    await db.flush()

    household = await db.get(Household, current_user.household_id)
    if household:
        await _recount_members(household, db)
        await _recompute_eating_mode(household, db)
    await db.flush()
    await db.refresh(member)

    return HouseholdMemberResponse.from_orm_with_flags(member)


@router.get("/members", response_model=list[HouseholdMemberResponse])
async def list_household_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all head-managed member profiles for the current household."""
    if not current_user.household_id:
        raise HTTPException(status_code=404, detail="Not in a household")

    result = await db.execute(
        select(HouseholdMember)
        .where(HouseholdMember.household_id == current_user.household_id)
        .order_by(HouseholdMember.created_at)
    )
    members = result.scalars().all()
    return [HouseholdMemberResponse.from_orm_with_flags(m) for m in members]


@router.put("/members/{member_id}", response_model=HouseholdMemberResponse)
async def update_household_member(
    member_id: uuid.UUID,
    request: HouseholdMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a family member's profile."""
    await _require_head(current_user)

    result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == current_user.household_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in your household")

    # Apply only the non-None fields from the request
    update_fields = request.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(member, field, value)

    calculate_and_store_bmi(member)

    eating_mode_changed = "eating_mode" in update_fields
    member_type_changed = "member_type" in update_fields

    await db.flush()

    if eating_mode_changed or member_type_changed:
        household = await db.get(Household, current_user.household_id)
        if household:
            if eating_mode_changed:
                await _recompute_eating_mode(household, db)
            if member_type_changed:
                await _recount_members(household, db)
        await db.flush()

    await db.refresh(member)
    return HouseholdMemberResponse.from_orm_with_flags(member)


@router.delete("/members/{member_id}", status_code=204)
async def delete_household_member(
    member_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a family member profile. Cascades to delete their wellness signals."""
    await _require_head(current_user)

    result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == current_user.household_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in your household")

    await db.delete(member)
    await db.flush()

    household = await db.get(Household, current_user.household_id)
    if household:
        await _recount_members(household, db)
        await _recompute_eating_mode(household, db)
    await db.flush()


# ── Wellness signals for HouseholdMembers ────────────────────────────────────

@router.post("/members/{member_id}/signals",
             response_model=MemberSignalResponse, status_code=201)
async def log_member_signal(
    member_id: uuid.UUID,
    request: MemberSignalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log a daily wellness signal for a household member. Upserts by (member_id, date)."""
    if not current_user.household_id:
        raise HTTPException(status_code=400, detail="Not in a household")

    result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == current_user.household_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in your household")

    signal_date = request.signal_date or date.today()

    # Upsert: update today's row if it exists, otherwise insert
    existing_result = await db.execute(
        select(HouseholdMemberSignal).where(
            HouseholdMemberSignal.member_id == member_id,
            HouseholdMemberSignal.signal_date == signal_date,
        )
    )
    signal = existing_result.scalar_one_or_none()

    if signal is None:
        signal = HouseholdMemberSignal(member_id=member_id, signal_date=signal_date)
        db.add(signal)

    update_data = request.model_dump(exclude_unset=True, exclude={"signal_date"})
    for field, value in update_data.items():
        setattr(signal, field, value)

    # If weight updated in signal, mirror it to member profile
    if request.weight_kg is not None:
        member.weight_kg = request.weight_kg
        calculate_and_store_bmi(member)

    await db.flush()
    await db.refresh(signal)
    return signal


@router.get("/members/{member_id}/signals",
            response_model=list[MemberSignalResponse])
async def get_member_signals(
    member_id: uuid.UUID,
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return up to `days` days of wellness signals for a household member."""
    if not current_user.household_id:
        raise HTTPException(status_code=400, detail="Not in a household")

    result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == current_user.household_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Member not found in your household")

    cutoff = date.today() - timedelta(days=min(days, 30))
    signals_result = await db.execute(
        select(HouseholdMemberSignal)
        .where(
            HouseholdMemberSignal.member_id == member_id,
            HouseholdMemberSignal.signal_date >= cutoff,
        )
        .order_by(HouseholdMemberSignal.signal_date.desc())
    )
    return signals_result.scalars().all()
