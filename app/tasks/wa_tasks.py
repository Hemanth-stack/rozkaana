import asyncio
import logging
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from app.tasks.celery_app import celery_app
from app.database import SyncSessionLocal

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


@celery_app.task
def send_all_whatsapp():
    from app.models.daily_menu import DailyMenu
    today = date.today()
    with get_sync_session() as db:
        menus = db.query(DailyMenu).filter(
            DailyMenu.menu_date == today,
            DailyMenu.wa_sent_at.is_(None),
            DailyMenu.pdf_key.isnot(None),
        ).all()
        for menu in menus:
            send_single_whatsapp.delay(str(menu.id))
    logger.info("Queued WhatsApp send for %d menus", len(menus))


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def send_single_whatsapp(self, menu_id: str):
    from app.models.daily_menu import DailyMenu
    from app.models.user import User
    from app.models.household import Household
    from app.utils.minio_client import get_presigned_url
    from app.services.whatsapp_service import wa_service
    import uuid as _uuid

    try:
        with get_sync_session() as db:
            menu = db.query(DailyMenu).get(_uuid.UUID(menu_id))
            if not menu or not menu.pdf_key:
                logger.error("Menu %s not found or has no PDF", menu_id)
                return

            if menu.owner_type == "household":
                household = db.query(Household).get(menu.owner_id)
                if household and household.head_user_id:
                    user = db.query(User).get(household.head_user_id)
                else:
                    user = None
            else:
                user = db.query(User).get(menu.owner_id)

            if not user or not user.wa_phone or not user.wa_opted_in:
                logger.info("Skipping WA for menu %s — user has no opted-in WA phone", menu_id)
                menu.wa_status = "skipped"
                return

            pdf_url = get_presigned_url(menu.pdf_key)

            async def _send():
                return await wa_service.send_meal_plan(
                    phone=user.wa_phone,
                    name=user.name or "there",
                    pdf_url=pdf_url,
                    menu_date=menu.menu_date,
                )

            success = asyncio.run(_send())

            if success:
                menu.wa_sent_at = datetime.utcnow()
                menu.wa_status = "sent"
                logger.info("WA sent for menu %s", menu_id)
            else:
                menu.wa_status = "failed"
                raise self.retry(exc=RuntimeError("WATI send returned failure"))

    except Exception as exc:
        if not hasattr(exc, "celery_retries"):
            with get_sync_session() as db:
                import uuid as _uuid2
                m = db.query(DailyMenu).get(_uuid2.UUID(menu_id))
                if m:
                    m.wa_status = "failed"
        raise self.retry(exc=exc)


@celery_app.task
def send_trial_expiry_warnings():
    from app.models.subscription import Subscription
    from app.models.user import User
    from app.services.whatsapp_service import wa_service

    today = date.today()
    warning_date = today + timedelta(days=2)

    with get_sync_session() as db:
        subs = db.query(Subscription).filter(
            Subscription.status == "trial",
            Subscription.trial_end == warning_date,
        ).all()

        for sub in subs:
            user = db.query(User).get(sub.user_id)
            if not user or not user.wa_phone or not user.wa_opted_in:
                continue

            async def _send(u=user, s=sub):
                await wa_service.send_template(
                    u.wa_phone,
                    "rozkaana_trial_expiry",
                    {"name": u.name or "there", "trial_end": str(s.trial_end)},
                )

            asyncio.run(_send())
            logger.info("Sent trial expiry warning to user %s", user.id)
