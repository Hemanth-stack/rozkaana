from fastapi import APIRouter, Depends
from app.schemas.user import UserProfile, UpdateBasicRequest, UpdateHealthRequest, UpdateEatingRequest, UpdateWhatsAppRequest
from app.dependencies import get_current_user
from app.models.user import User
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.get("/me", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me/basic")
async def update_basic(request: UpdateBasicRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Update fields and recalc BMI
    pass

@router.put("/me/health")
async def update_health(request: UpdateHealthRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Update tags
    pass

@router.put("/me/eating")
async def update_eating(request: UpdateEatingRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Update eating prefs
    pass

@router.put("/me/whatsapp")
async def update_whatsapp(request: UpdateWhatsAppRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Update WA and opt-in
    pass

@router.post("/me/onboarding-complete")
async def complete_onboarding(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Mark complete and create trial sub
    pass