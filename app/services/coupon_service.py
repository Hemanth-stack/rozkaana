from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.coupon import Coupon, CouponRedemption
from app.services.subscription_service import PLAN_AMOUNTS


async def validate_coupon(
    code: str,
    plan_type: str,
    user_id: UUID,
    db: AsyncSession,
) -> dict:
    """Validate a coupon code for a given plan and user. Returns discount info."""
    result = await db.execute(select(Coupon).where(Coupon.code == code.upper()))
    coupon = result.scalar_one_or_none()

    if not coupon or not coupon.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon code")

    today = date.today()
    if coupon.valid_from and today < coupon.valid_from:
        raise HTTPException(status_code=400, detail="Coupon is not yet active")
    if coupon.valid_until and today > coupon.valid_until:
        raise HTTPException(status_code=400, detail="Coupon has expired")

    if coupon.max_redemptions is not None and coupon.redeemed_count >= coupon.max_redemptions:
        raise HTTPException(status_code=400, detail="Coupon redemption limit reached")

    if coupon.applicable_plans and plan_type not in coupon.applicable_plans:
        raise HTTPException(status_code=400, detail="Coupon is not valid for this plan")

    # Check if this user already redeemed this coupon
    existing = await db.execute(
        select(CouponRedemption).where(
            CouponRedemption.coupon_id == coupon.id,
            CouponRedemption.user_id == user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You have already used this coupon")

    original_amount = PLAN_AMOUNTS.get(plan_type, 0)

    if coupon.discount_type == "percent_off":
        pct = min(coupon.discount_value, 100)
        discounted = int(original_amount * (1 - pct / 100))
        return {
            "coupon": coupon,
            "discount_type": "percent_off",
            "discount_value": pct,
            "original_amount": original_amount,
            "discounted_amount": discounted,
            "free_days": 0,
            "message": f"{pct}% off applied — ₹{discounted // 100} instead of ₹{original_amount // 100}",
        }
    else:  # free_days
        return {
            "coupon": coupon,
            "discount_type": "free_days",
            "discount_value": coupon.discount_value,
            "original_amount": 0,
            "discounted_amount": 0,
            "free_days": coupon.discount_value,
            "message": f"{coupon.discount_value} free days added to your subscription",
        }


async def record_redemption(
    coupon: Coupon,
    user_id: UUID,
    plan_type: str,
    db: AsyncSession,
) -> None:
    """Record a coupon redemption and increment the counter."""
    redemption = CouponRedemption(
        coupon_id=coupon.id,
        user_id=user_id,
        plan_type=plan_type,
    )
    db.add(redemption)
    coupon.redeemed_count = (coupon.redeemed_count or 0) + 1
    await db.flush()


async def apply_free_days_coupon(
    code: str,
    plan_type: str,
    user_id: UUID,
    db: AsyncSession,
) -> dict:
    """Apply a free_days coupon without any payment. Extends trial or creates active period."""
    from datetime import timedelta
    from sqlalchemy.future import select
    from app.models.subscription import Subscription

    info = await validate_coupon(code, plan_type, user_id, db)
    coupon = info["coupon"]

    if coupon.discount_type != "free_days":
        raise HTTPException(status_code=400, detail="This coupon requires a payment — use checkout flow")

    free_days = coupon.discount_value
    today = date.today()

    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()

    if sub:
        if sub.status == "trial":
            # Extend trial end
            current_end = sub.trial_end or today
            sub.trial_end = current_end + timedelta(days=free_days)
        elif sub.status in ("active",):
            # Extend period end
            current_end = sub.current_period_end or today
            sub.current_period_end = current_end + timedelta(days=free_days)
        elif sub.status in ("cancelled", "expired"):
            # Reactivate with free days
            sub.plan_type = plan_type
            sub.status = "active"
            sub.current_period_start = today
            sub.current_period_end = today + timedelta(days=free_days)
            sub.trial_end = None
        else:
            raise HTTPException(status_code=400, detail="Cannot apply coupon to a paused subscription")
    else:
        sub = Subscription(
            user_id=user_id,
            plan_type=plan_type,
            status="active",
            current_period_start=today,
            current_period_end=today + timedelta(days=free_days),
        )
        db.add(sub)

    await db.flush()
    await record_redemption(coupon, user_id, plan_type, db)

    return {
        "message": f"{free_days} free days applied successfully",
        "plan_type": sub.plan_type,
        "status": sub.status,
        "period_end": str(sub.current_period_end or sub.trial_end),
    }
