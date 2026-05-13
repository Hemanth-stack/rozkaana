import asyncio
import logging
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from app.tasks.celery_app import celery_app
from app.database import SyncSessionLocal
from app.config import settings

logger = logging.getLogger(__name__)


@contextmanager
def get_sync_session():
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_all_menus(self):
    from app.models.subscription import Subscription
    from app.models.daily_menu import DailyMenu
    from app.models.user import User

    tomorrow = date.today() + timedelta(days=1)
    seen_owners: set = set()

    with get_sync_session() as db:
        subs = db.query(Subscription).filter(
            Subscription.status.in_(["trial", "active"])
        ).all()

        for sub in subs:
            user = db.query(User).get(sub.user_id)
            if not user or not user.is_active:
                continue

            owner_id = str(user.household_id or user.id)
            owner_type = "household" if user.household_id else "user"

            if owner_id in seen_owners:
                continue
            seen_owners.add(owner_id)

            import uuid as _uuid
            existing = db.query(DailyMenu).filter(
                DailyMenu.owner_id == _uuid.UUID(owner_id),
                DailyMenu.menu_date == tomorrow,
            ).first()
            if existing:
                logger.debug("Menu already exists for owner=%s date=%s — skipping", owner_id, tomorrow)
                continue

            generate_single_menu.delay(owner_id, owner_type, str(tomorrow), None)
            logger.info("Queued menu generation for owner=%s type=%s", owner_id, owner_type)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_single_menu(self, owner_id: str, owner_type: str, menu_date_str: str, cuisine_override: str | None = None):
    from app.models.daily_menu import DailyMenu
    from app.services.menu_engine import generate_menu
    from app.utils.redis_client import sync_redis_client
    import redis as sync_redis_module
    import uuid as _uuid

    menu_date = date.fromisoformat(menu_date_str)

    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker as async_sm
        import redis.asyncio as aioredis

        async def _run():
            engine = create_async_engine(settings.DATABASE_URL, echo=False)
            async_session = async_sm(engine, class_=AsyncSession, expire_on_commit=False)
            redis_conn = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

            try:
                async with async_session() as session:
                    menu_data = await generate_menu(
                        session, redis_conn, owner_id, owner_type, menu_date, cuisine_override
                    )
                    await session.commit()
                    return menu_data
            finally:
                await redis_conn.aclose()
                await engine.dispose()

        menu_data = asyncio.run(_run())

    except Exception as exc:
        logger.error("Menu generation failed for owner=%s: %s", owner_id, exc)
        raise self.retry(exc=exc)

    with get_sync_session() as db:
        import uuid as _uuid2
        existing = db.query(DailyMenu).filter(
            DailyMenu.owner_id == _uuid2.UUID(owner_id),
            DailyMenu.menu_date == menu_date,
        ).first()

        if existing:
            for k, v in menu_data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            existing.is_regenerated = True
            existing.pdf_key = None
            existing.email_sent_at = None
            existing.email_status = None
            menu_id = str(existing.id)
        else:
            new_menu = DailyMenu(**menu_data)
            db.add(new_menu)
            db.flush()
            menu_id = str(new_menu.id)

    build_pdf_task = __import__("app.tasks.pdf_tasks", fromlist=["build_single_pdf"]).build_single_pdf
    build_pdf_task.delay(menu_id)
    return menu_id


@celery_app.task
def expire_subscriptions():
    from app.models.subscription import Subscription
    today = date.today()

    with get_sync_session() as db:
        expired_trials = db.query(Subscription).filter(
            Subscription.status == "trial",
            Subscription.trial_end < today,
        ).all()
        for sub in expired_trials:
            sub.status = "expired"

        expired_active = db.query(Subscription).filter(
            Subscription.status == "active",
            Subscription.current_period_end < today,
        ).all()
        for sub in expired_active:
            sub.status = "expired"

    logger.info("Expired %d trials, %d active subs", len(expired_trials), len(expired_active))


@celery_app.task
def clean_expired_otps():
    from app.models.otp_session import OTPSession
    with get_sync_session() as db:
        deleted = db.query(OTPSession).filter(OTPSession.expires_at < datetime.utcnow()).delete()
    logger.info("Cleaned %d expired OTP sessions", deleted)
