import hashlib
import hmac
import logging
from datetime import date, timedelta
from uuid import UUID

import razorpay
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.subscription import Subscription
from app.models.user import User

logger = logging.getLogger(__name__)

PLAN_AMOUNTS: dict[str, int] = {
    "solo_basic": 19900,   # ₹199 in paise
    "solo_pro":   39900,   # ₹399 in paise
    "family":     69900,   # ₹699 in paise
}

PLAN_LABELS: dict[str, str] = {
    "solo_basic": "Starter",
    "solo_pro":   "Pro",
    "family":     "Family",
}

_rzp_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


async def create_trial(user_id: UUID, plan_type: str, db: AsyncSession) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    today = date.today()
    sub = Subscription(
        user_id=user_id,
        plan_type=plan_type,
        status="trial",
        trial_start=today,
        trial_end=today + timedelta(days=7),
        pause_days_used=0,
    )
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return sub


async def create_checkout_order(
    user_id: UUID,
    plan_type: str,
    db: AsyncSession,
    coupon_code: str | None = None,
) -> dict:
    """Create a Razorpay Order for one month of the given plan, optionally with a coupon."""
    original_amount = PLAN_AMOUNTS.get(plan_type)
    if not original_amount:
        raise HTTPException(status_code=400, detail="Invalid plan type")

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    amount = original_amount
    applied_coupon = None

    if coupon_code:
        from app.services.coupon_service import validate_coupon
        info = await validate_coupon(coupon_code, plan_type, user_id, db)
        if info["discount_type"] == "percent_off":
            amount = info["discounted_amount"]
            applied_coupon = info["coupon"]
        # free_days coupons should use the apply-free-coupon endpoint, not checkout

    try:
        order = _rzp_client.order.create({
            "amount": amount,
            "currency": "INR",
            "notes": {
                "plan_type": plan_type,
                "user_id": str(user_id),
                "coupon_code": coupon_code or "",
            },
        })
    except Exception as exc:
        logger.error("Razorpay order creation failed for user %s: %s", user_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Payment gateway error")

    return {
        "order_id": order["id"],
        "amount": amount,
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID,
        "user_name": user.name or "",
        "user_email": user.email or "",
        "plan_type": plan_type,
        "plan_label": PLAN_LABELS.get(plan_type, plan_type),
        "coupon_code": coupon_code,
        "original_amount": original_amount,
        "_applied_coupon": applied_coupon,   # internal — not in response schema
    }


async def verify_and_activate(
    user_id: UUID,
    razorpay_payment_id: str,
    razorpay_order_id: str,
    razorpay_signature: str,
    db: AsyncSession,
) -> Subscription:
    """Verify Razorpay HMAC signature and activate the subscription."""
    # Verify HMAC-SHA256(key_secret, order_id|payment_id)
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, razorpay_signature):
        raise HTTPException(status_code=400, detail="Payment verification failed — invalid signature")

    # Fetch order from Razorpay to read the authoritative plan_type (prevents spoofing)
    try:
        order = _rzp_client.order.fetch(razorpay_order_id)
        plan_type = order["notes"].get("plan_type")
    except Exception as exc:
        logger.error("Razorpay order fetch failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment gateway error")

    if not plan_type or plan_type not in PLAN_AMOUNTS:
        raise HTTPException(status_code=400, detail="Invalid order — plan not found")

    # Activate subscription
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    today = date.today()

    if sub:
        sub.plan_type = plan_type
        sub.status = "active"
        sub.current_period_start = today
        sub.current_period_end = today + timedelta(days=30)
        sub.rzp_subscription_id = razorpay_payment_id
    else:
        sub = Subscription(
            user_id=user_id,
            plan_type=plan_type,
            status="active",
            current_period_start=today,
            current_period_end=today + timedelta(days=30),
            rzp_subscription_id=razorpay_payment_id,
        )
        db.add(sub)

    await db.flush()

    # Record coupon redemption if a percent_off coupon was applied
    coupon_code = order["notes"].get("coupon_code", "") if "order" in dir() else ""
    if coupon_code:
        try:
            from app.models.coupon import Coupon, CouponRedemption
            coupon_result = await db.execute(select(Coupon).where(Coupon.code == coupon_code))
            coupon = coupon_result.scalar_one_or_none()
            if coupon:
                already = await db.execute(
                    select(CouponRedemption).where(
                        CouponRedemption.coupon_id == coupon.id,
                        CouponRedemption.user_id == user_id,
                    )
                )
                if not already.scalar_one_or_none():
                    db.add(CouponRedemption(coupon_id=coupon.id, user_id=user_id, plan_type=plan_type))
                    coupon.redeemed_count = (coupon.redeemed_count or 0) + 1
                    await db.flush()
        except Exception as exc:
            logger.warning("Coupon redemption recording failed after payment: %s", exc)

    await db.refresh(sub)
    return sub


async def handle_razorpay_webhook(event: str, payload: dict, db: AsyncSession) -> None:
    if event == "payment.captured":
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment.get("order_id")
        if not order_id:
            return
        try:
            order = _rzp_client.order.fetch(order_id)
            user_id_str = order["notes"].get("user_id")
            plan_type = order["notes"].get("plan_type")
        except Exception as exc:
            logger.warning("Webhook: order fetch failed for order_id=%s: %s", order_id, exc)
            return

        if not user_id_str or not plan_type:
            return

        from uuid import UUID as _UUID
        try:
            uid = _UUID(user_id_str)
        except ValueError:
            return

        result = await db.execute(select(Subscription).where(Subscription.user_id == uid))
        sub = result.scalar_one_or_none()
        today = date.today()
        if sub:
            sub.status = "active"
            sub.plan_type = plan_type
            sub.current_period_start = today
            sub.current_period_end = today + timedelta(days=30)
            sub.rzp_subscription_id = payment.get("id")
        await db.flush()
        return

    # Handle legacy subscription events (if Razorpay Subscriptions are ever used)
    subscription_data = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    rzp_sub_id = subscription_data.get("id")
    if not rzp_sub_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.rzp_subscription_id == rzp_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning("Webhook: no subscription for rzp_id=%s", rzp_sub_id)
        return

    if event == "subscription.activated":
        sub.status = "active"
        _set_period_from_payload(sub, subscription_data)
    elif event == "subscription.charged":
        sub.status = "active"
        _set_period_from_payload(sub, subscription_data)
    elif event == "subscription.cancelled":
        sub.status = "cancelled"
    elif event == "subscription.halted":
        sub.status = "paused"
    elif event == "payment.failed":
        logger.warning("Payment failed for rzp_sub=%s", rzp_sub_id)

    await db.flush()


def _set_period_from_payload(sub: Subscription, data: dict) -> None:
    from datetime import datetime
    start_ts = data.get("current_start")
    end_ts = data.get("current_end")
    if start_ts:
        sub.current_period_start = datetime.fromtimestamp(int(start_ts)).date()
    if end_ts:
        sub.current_period_end = datetime.fromtimestamp(int(end_ts)).date()


async def pause_subscription(user_id: UUID, db: AsyncSession) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")
    if sub.status != "active":
        raise HTTPException(status_code=400, detail="Subscription is not active")
    if (sub.pause_days_used or 0) >= 30:
        raise HTTPException(status_code=400, detail="Pause limit (30 days/year) reached")

    sub.status = "paused"
    sub.paused_at = date.today()
    await db.flush()
    return sub


async def resume_subscription(user_id: UUID, db: AsyncSession) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")
    if sub.status != "paused":
        raise HTTPException(status_code=400, detail="Subscription is not paused")

    if sub.paused_at:
        days_paused = (date.today() - sub.paused_at).days
        sub.pause_days_used = (sub.pause_days_used or 0) + days_paused

    sub.status = "active"
    sub.paused_at = None
    await db.flush()
    return sub


async def cancel_subscription(user_id: UUID, db: AsyncSession) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")

    sub.status = "cancelled"
    await db.flush()
    return sub


async def check_and_expire_trials(db: AsyncSession) -> int:
    today = date.today()
    result = await db.execute(
        select(Subscription).where(
            Subscription.status == "trial",
            Subscription.trial_end < today,
        )
    )
    subs = result.scalars().all()
    for sub in subs:
        sub.status = "expired"
    await db.flush()
    return len(subs)
