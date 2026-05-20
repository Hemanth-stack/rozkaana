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
    CancelResponse, CheckoutRequest, CheckoutResponse,
    PauseResponse, ResumeResponse, SubscriptionResponse,
    VerifyPaymentRequest,
)
from app.schemas.coupon import ValidateCouponRequest, ValidateCouponResponse
from app.services import subscription_service

router = APIRouter(prefix="/subscription", tags=["subscription"])

VALID_PLANS = {"solo_basic", "solo_pro", "family"}


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


@router.post("/upgrade", response_model=CheckoutResponse)
async def upgrade_subscription(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Backward-compat alias for /create-checkout — handles cached browser clients."""
    if request.plan_type not in VALID_PLANS:
        raise HTTPException(status_code=400, detail=f"plan_type must be one of: {VALID_PLANS}")
    return await subscription_service.create_checkout_order(current_user.id, request.plan_type, db, request.coupon_code)


@router.post("/create-checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request.plan_type not in VALID_PLANS:
        raise HTTPException(status_code=400, detail=f"plan_type must be one of: {VALID_PLANS}")
    result = await subscription_service.create_checkout_order(current_user.id, request.plan_type, db, request.coupon_code)
    return result


@router.post("/validate-coupon", response_model=ValidateCouponResponse)
async def validate_coupon_endpoint(
    request: ValidateCouponRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request.plan_type not in VALID_PLANS:
        raise HTTPException(status_code=400, detail=f"plan_type must be one of: {VALID_PLANS}")
    from app.services.coupon_service import validate_coupon
    info = await validate_coupon(request.code, request.plan_type, current_user.id, db)
    return ValidateCouponResponse(
        valid=True,
        discount_type=info["discount_type"],
        discount_value=info["discount_value"],
        original_amount=info["original_amount"],
        discounted_amount=info["discounted_amount"],
        free_days=info["free_days"],
        message=info["message"],
    )


@router.post("/apply-coupon")
async def apply_free_coupon(
    request: ValidateCouponRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply a free_days coupon — no payment required."""
    if request.plan_type not in VALID_PLANS:
        raise HTTPException(status_code=400, detail=f"plan_type must be one of: {VALID_PLANS}")
    from app.services.coupon_service import apply_free_days_coupon
    return await apply_free_days_coupon(request.code, request.plan_type, current_user.id, db)


@router.post("/verify-payment", response_model=SubscriptionResponse)
async def verify_payment(
    request: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await subscription_service.verify_and_activate(
        current_user.id,
        request.razorpay_payment_id,
        request.razorpay_order_id,
        request.razorpay_signature,
        db,
    )
    if current_user.email and current_user.email_verified:
        try:
            from app.services.email_service import email_service
            from app.services.subscription_service import PLAN_LABELS
            await email_service.send_subscription_upgraded(
                current_user.email,
                current_user.name or "there",
                PLAN_LABELS.get(sub.plan_type, sub.plan_type),
                str(sub.current_period_end or ""),
            )
        except Exception:
            pass
    return sub


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
    if current_user.email and current_user.email_verified:
        try:
            from app.services.email_service import email_service
            active_until = str(sub.current_period_end or sub.trial_end or "")
            await email_service.send_subscription_cancelled(
                current_user.email, current_user.name or "there", active_until
            )
        except Exception:
            pass
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
