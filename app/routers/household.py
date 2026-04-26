from fastapi import APIRouter, Depends
from app.schemas.household import HouseholdCreate, HouseholdResponse, InviteResponse, UpdatePreferencesRequest
from app.dependencies import get_current_user
from app.models.user import User
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.post("/", response_model=HouseholdResponse)
async def create_household(request: HouseholdCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Create household
    pass

@router.get("/", response_model=HouseholdResponse)
async def get_household(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Get household
    pass

@router.post("/invite", response_model=InviteResponse)
async def invite_member(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Generate invite
    pass

@router.post("/join/{token}")
async def join_household(token: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Join via token
    pass

@router.delete("/member/{user_id}")
async def remove_member(user_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Remove member
    pass

@router.put("/preferences")
async def update_preferences(request: UpdatePreferencesRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Update prefs
    pass