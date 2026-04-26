import hmac
import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import (
    CancelResponse, PauseResponse, ResumeResponse,
    SubscriptionResponse, UpgradeRequest, UpgradeResponse,
)
from app.services import subscription_service

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Subscription).where(Subscription.user_id == current_user.id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")
    return sub


@router.post("/upgrade", response_model=UpgradeResponse)
async def upgrade_plan(
    request: UpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid_plans = {"solo_basic", "solo_pro", "family"}
    if request.plan_type not in valid_plans:
        raise HTTPException(status_code=400, detail=f"plan_type must be one of: {valid_plans}")
    result = await subscription_service.upgrade_plan(current_user.id, request.plan_type, db)
    return result


@router.post("/pause", response_model=PauseResponse)
async def pause_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await subscription_service.pause_subscription(current_user.id, db)
    return PauseResponse(message="Subscription paused", paused_at=sub.paused_at)


@router.post("/resume", response_model=ResumeResponse)
async def resume_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await subscription_service.resume_subscription(current_user.id, db)
    return ResumeResponse(message="Subscription resumed", status=sub.status)


@router.post("/cancel", response_model=CancelResponse)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await subscription_service.cancel_subscription(current_user.id, db)
    return CancelResponse(message="Subscription cancelled", status=sub.status)


@router.post("/webhook/razorpay", status_code=200)
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
):
    body = await request.body()
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_razorpay_signature or ""):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook signature")

    payload = await request.json()
    event = payload.get("event", "")
    await subscription_service.handle_razorpay_webhook(event, payload, db)
    return {"status": "ok"}
