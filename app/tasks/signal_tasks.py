import asyncio
import logging
from contextlib import contextmanager

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


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def prompt_users_for_signals(self):
    """
    Every 3 days: send a WhatsApp message to all opted-in users asking them
    to log their daily wellness signals (energy, sleep, digestion, flags).
    """
    from app.models.user import User
    from app.models.subscription import Subscription
    from app.services.whatsapp_service import WhatsAppService

    wa = WhatsAppService()
    app_url = getattr(settings, "APP_URL", "https://rozkaana.com/app")

    prompted = 0
    failed = 0

    with get_sync_session() as db:
        active_subs = db.query(Subscription).filter(
            Subscription.status.in_(["trial", "active"])
        ).all()

        for sub in active_subs:
            user = db.query(User).get(sub.user_id)
            if not user or not user.is_active or not user.onboarding_complete:
                continue
            if not user.wa_opted_in or not user.wa_phone:
                continue

            name = user.name or "there"
            message = (
                f"Hi {name}! 👋\n\n"
                f"How are you feeling today? Log your energy, sleep quality & wellness "
                f"to help us keep your meal plan on track.\n\n"
                f"It takes just 30 seconds → {app_url}\n\n"
                f"_(Reply STOP to unsubscribe)_"
            )
            try:
                asyncio.run(wa.send_text(user.wa_phone, message))
                prompted += 1
            except Exception as exc:
                logger.warning("WA prompt failed for user=%s: %s", user.id, exc)
                failed += 1

    logger.info("Signal prompt sent: %d prompted, %d failed", prompted, failed)
    return {"prompted": prompted, "failed": failed}


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def analyze_all_users_signals(self):
    """
    Every 3 days (4h after prompt): analyse accumulated signals for all active users,
    auto-update health_tags where deficiency patterns are detected, recalculate
    macro targets, and queue tomorrow's menu regeneration for affected users.
    """
    from app.models.user import User
    from app.models.subscription import Subscription

    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker as async_sm
        from app.services.signal_analysis_service import analyze_and_update_user

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async_session_maker = async_sm(engine, class_=AsyncSession, expire_on_commit=False)

        updated = 0
        skipped = 0

        with get_sync_session() as sync_db:
            active_subs = sync_db.query(Subscription).filter(
                Subscription.status.in_(["trial", "active"])
            ).all()
            user_ids = [sub.user_id for sub in active_subs]

        try:
            for user_id in user_ids:
                try:
                    async with async_session_maker() as session:
                        result = await analyze_and_update_user(user_id, session)
                        await session.commit()
                        if result["tags_added"]:
                            updated += 1
                            logger.info("Tags auto-updated for user=%s: %s", user_id, result["tags_added"])
                        else:
                            skipped += 1
                except Exception as exc:
                    logger.error("Signal analysis failed for user=%s: %s", user_id, exc)
                    skipped += 1
        finally:
            await engine.dispose()

        return {"users_updated": updated, "users_skipped": skipped}

    result = asyncio.run(_run())
    logger.info("Signal analysis complete: %s", result)
    return result
