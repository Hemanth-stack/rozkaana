from app.tasks.celery_app import app
from app.database import get_sync_db
from app.models.subscription import Subscription
from app.models.daily_menu import DailyMenu
from app.models.user import User
from app.models.otp_session import OTPSession
from app.services.menu_engine import generate_menu
from app.utils.redis_client import redis_client
from datetime import date, timedelta, datetime
import asyncio

@app.task(bind=True, max_retries=2)
def generate_all_menus(self):
    with get_sync_db() as db:
        tomorrow = date.today() + timedelta(days=1)

        # 1. Get all active subscribers (not paused, not expired)
        active_subs = db.query(Subscription).filter(
            Subscription.status.in_(["trial", "active"])
        ).all()

        for sub in active_subs:
            user = sub.user
            owner_id = user.household_id or str(user.id)
            owner_type = "household" if user.household_id else "user"

            # Skip if already generated (idempotent — safe to retry)
            existing = db.query(DailyMenu).filter(
                DailyMenu.owner_id == owner_id,
                DailyMenu.menu_date == tomorrow
            ).first()
            if existing: continue

            # Enqueue individual menu generation as separate task
            generate_single_menu.delay(owner_id, owner_type, str(tomorrow))

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_single_menu(self, owner_id, owner_type, menu_date_str):
    try:
        menu_date = date.fromisoformat(menu_date_str)
        async def _gen():
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            from app.config import settings
            engine = create_async_engine(settings.database_url)
            async with AsyncSession(engine) as db:
                return await generate_menu(db, redis_client, owner_id, owner_type, menu_date)
        menu = asyncio.run(_gen())
        with get_sync_db() as db:
            db_menu = DailyMenu(**menu)
            db.add(db_menu)
            db.commit()
    except Exception as exc:
        raise self.retry(exc=exc)

@app.task
def clean_expired_otps():
    with get_sync_db() as db:
        db.query(OTPSession).filter(OTPSession.expires_at < datetime.utcnow()).delete()
        db.commit()

@app.task
def expire_subscriptions():
    with get_sync_db() as db:
        db.query(Subscription).filter(
            Subscription.status == "cancelled",
            Subscription.current_period_end < date.today()
        ).update({"status": "expired"})
        db.commit()