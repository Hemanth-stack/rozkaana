import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.household import Household
from app.models.user import User
from app.schemas.household import (
    HouseholdCreate, HouseholdResponse, InviteResponse, UpdatePreferencesRequest,
)
from app.services.menu_engine import EATING_MODE_STRICTNESS
from app.utils.redis_client import get_redis, invite_token_key

router = APIRouter(prefix="/household", tags=["household"])


async def _build_household_response(household: Household, db: AsyncSession) -> dict:
    result = await db.execute(select(User).where(User.household_id == household.id))
    members = result.scalars().all()
    return {
        "id": household.id,
        "name": household.name,
        "head_user_id": household.head_user_id,
        "shared_eating_mode": household.shared_eating_mode,
        "member_count": household.member_count,
        "cuisine_prefs": household.cuisine_prefs or [],
        "members": members,
    }


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

    invite_url = f"{settings.APP_BASE_URL}/join/{token}"
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
        raise HTTPException(status_code=400, detail="Household is full (max 6 members)")

    current_user.household_id = household.id
    household.member_count = (household.member_count or 0) + 1

    result = await db.execute(select(User).where(User.household_id == household.id))
    all_members = result.scalars().all()
    modes = [m.eating_mode or "pure_veg" for m in all_members] + [current_user.eating_mode or "pure_veg"]
    household.shared_eating_mode = min(modes, key=lambda m: EATING_MODE_STRICTNESS.get(m, 99))

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
        result2 = await db.execute(select(User).where(User.household_id == household.id))
        remaining = result2.scalars().all()
        if remaining:
            modes = [m.eating_mode or "pure_veg" for m in remaining]
            household.shared_eating_mode = min(modes, key=lambda m: EATING_MODE_STRICTNESS.get(m, 99))

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
