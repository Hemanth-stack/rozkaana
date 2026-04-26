from fastapi import APIRouter, Depends
from app.schemas.subscription import SubscriptionResponse, UpgradeRequest, UpgradeResponse, PauseResponse, ResumeResponse, CancelResponse
from app.dependencies import get_current_user
from app.models.user import User
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.get("/", response_model=SubscriptionResponse)
async def get_subscription(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Get sub
    pass

@router.post("/upgrade", response_model=UpgradeResponse)
async def upgrade_plan(request: UpgradeRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Upgrade
    pass

@router.post("/pause", response_model=PauseResponse)
async def pause_subscription(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Pause
    pass

@router.post("/resume", response_model=ResumeResponse)
async def resume_subscription(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Resume
    pass

@router.post("/cancel", response_model=CancelResponse)
async def cancel_subscription(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Cancel
    pass

@router.post("/webhook/razorpay")
async def razorpay_webhook():
    # Handle webhook
    pass