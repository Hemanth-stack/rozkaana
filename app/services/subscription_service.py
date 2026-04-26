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

# Razorpay plan IDs per plan type (set in Razorpay dashboard, store in .env or hardcode for now)
RZP_PLAN_IDS: dict[str, str] = {
    "solo_basic": "plan_solo_basic",
    "solo_pro": "plan_solo_pro",
    "family": "plan_family",
}

# Approximate MRR per plan
PLAN_PRICES: dict[str, float] = {
    "solo_basic": 299.0,
    "solo_pro": 499.0,
    "family": 799.0,
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


async def upgrade_plan(user_id: UUID, plan_type: str, db: AsyncSession) -> dict:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        if not sub or not sub.rzp_customer_id:
            customer = _rzp_client.customer.create({
                "name": user.name or "Rozkaana User",
                "contact": user.phone.lstrip("+"),
            })
            rzp_customer_id = customer["id"]
        else:
            rzp_customer_id = sub.rzp_customer_id

        rzp_plan_id = RZP_PLAN_IDS.get(plan_type, "plan_solo_basic")

        rzp_sub = _rzp_client.subscription.create({
            "plan_id": rzp_plan_id,
            "customer_notify": 1,
            "quantity": 1,
            "total_count": 12,
            "customer_id": rzp_customer_id,
        })

        payment_link = f"https://rzp.io/l/{rzp_sub['id']}"

        if sub:
            sub.rzp_customer_id = rzp_customer_id
            sub.rzp_subscription_id = rzp_sub["id"]
            sub.rzp_plan_id = rzp_plan_id
            sub.plan_type = plan_type
        else:
            sub = Subscription(
                user_id=user_id,
                plan_type=plan_type,
                status="trial",
                rzp_customer_id=rzp_customer_id,
                rzp_subscription_id=rzp_sub["id"],
                rzp_plan_id=rzp_plan_id,
            )
            db.add(sub)

        await db.flush()

        return {
            "payment_link": payment_link,
            "rzp_subscription_id": rzp_sub["id"],
        }
    except Exception as exc:
        logger.error("Razorpay upgrade failed for user %s: %s", user_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Payment gateway error")


async def handle_razorpay_webhook(event: str, payload: dict, db: AsyncSession) -> None:
    subscription_data = (
        payload.get("payload", {}).get("subscription", {}).get("entity", {})
    )
    rzp_sub_id = subscription_data.get("id")

    if not rzp_sub_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.rzp_subscription_id == rzp_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning("Webhook: no subscription found for rzp_id=%s", rzp_sub_id)
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
        raise HTTPException(status_code=400, detail="Pause limit (30 days) reached")

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

    if sub.rzp_subscription_id:
        try:
            _rzp_client.subscription.cancel(sub.rzp_subscription_id, {"cancel_at_cycle_end": 1})
        except Exception as exc:
            logger.warning("Razorpay cancel failed: %s", exc)

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
