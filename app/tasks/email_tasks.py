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
def send_all_emails():
    """Send daily meal plan email to all users whose PDF is ready and email not yet sent.

    Runs at EMAIL_SEND_HOUR_UTC (default 00:00 UTC = 05:30 IST) for today's menus.
    Also sweeps yesterday in case a PDF was built late or a previous send failed.
    """
    from app.models.daily_menu import DailyMenu
    today = date.today()
    yesterday = today - timedelta(days=1)
    with get_sync_session() as db:
        menus = db.query(DailyMenu).filter(
            DailyMenu.menu_date >= yesterday,
            DailyMenu.menu_date <= today,
            DailyMenu.email_sent_at.is_(None),
            DailyMenu.pdf_key.isnot(None),
        ).all()
        for menu in menus:
            send_menu_email.delay(str(menu.id))
    logger.info("Queued menu email for %d menus (dates %s – %s)", len(menus), yesterday, today)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def send_menu_email(self, menu_id: str):
    """Send the daily meal plan email for one menu."""
    import uuid as _uuid
    from app.models.daily_menu import DailyMenu
    from app.models.user import User
    from app.models.household import Household
    from app.models.recipe import Recipe
    from app.services.email_service import email_service
    from app.config import settings

    try:
        with get_sync_session() as db:
            menu = db.query(DailyMenu).get(_uuid.UUID(menu_id))
            if not menu or not menu.pdf_key:
                logger.info("Skipping email for menu %s — no PDF", menu_id)
                return
            if menu.email_sent_at is not None:
                logger.info("Skipping email for menu %s — already sent at %s", menu_id, menu.email_sent_at)
                return

            if menu.owner_type == "household":
                household = db.query(Household).get(menu.owner_id)
                user = db.query(User).get(household.head_user_id) if household else None
            else:
                user = db.query(User).get(menu.owner_id)

            if not user or not user.email or not user.email_verified:
                logger.info("Skipping email for menu %s — no verified email", menu_id)
                menu.email_status = "skipped"
                return

            # Build recipe dict for template
            slot_map = {
                "breakfast": menu.breakfast_id,
                "morning_snack": menu.morning_snack_id,
                "lunch": menu.lunch_id,
                "evening_snack": menu.evening_snack_id,
                "dinner": menu.dinner_id,
            }
            recipe_ids = [v for v in slot_map.values() if v]
            recipe_objs = {str(r.id): r for r in db.query(Recipe).filter(Recipe.id.in_(recipe_ids)).all()}

            menu_dict = {
                "total_calories": menu.total_calories or 0,
                "total_protein_g": float(menu.total_protein_g or 0),
                "total_carbs_g": float(menu.total_carbs_g or 0),
                "total_fat_g": float(menu.total_fat_g or 0),
            }
            for slot, rid in slot_map.items():
                r = recipe_objs.get(str(rid)) if rid else None
                menu_dict[slot] = {"name": r.name, "calories": r.calories} if r else None

            pdf_url = f"{settings.APP_BASE_URL}/files/{menu.pdf_key}"

            # Read PDF bytes for attachment
            from app.utils.minio_client import _client, settings as _s
            pdf_bytes = None
            try:
                resp = _client.get_object(_s.MINIO_BUCKET_NAME, menu.pdf_key)
                pdf_bytes = resp.read()
            except Exception as exc:
                logger.warning("Could not fetch PDF bytes for attachment: %s", exc)

            async def _send():
                return await email_service.send_menu_card(
                    to=user.email,
                    name=user.name or "there",
                    menu_date=menu.menu_date,
                    menu=menu_dict,
                    pdf_bytes=pdf_bytes,
                    pdf_url=pdf_url,
                )

            success = asyncio.run(_send())

            if success:
                menu.email_sent_at = datetime.utcnow()
                menu.email_status = "sent"
                logger.info("Menu email sent to %s for %s", user.email, menu_id)
            else:
                menu.email_status = "failed"
                raise self.retry(exc=RuntimeError("Email send failed"))

    except Exception as exc:
        logger.error("send_menu_email failed for %s: %s", menu_id, exc)
        raise self.retry(exc=exc)


@celery_app.task
def send_trial_expiry_warnings():
    """Send trial expiry warning emails 2 days before trial ends."""
    from app.models.subscription import Subscription
    from app.models.user import User
    from app.services.email_service import email_service

    today = date.today()
    warning_date = today + timedelta(days=2)

    with get_sync_session() as db:
        subs = db.query(Subscription).filter(
            Subscription.status == "trial",
            Subscription.trial_end == warning_date,
        ).all()
        for sub in subs:
            user = db.query(User).get(sub.user_id)
            if not user or not user.email or not user.email_verified:
                continue
            async def _send(u=user, s=sub):
                await email_service.send_trial_expiry_warning(
                    u.email, u.name or "there", str(s.trial_end)
                )
            asyncio.run(_send())
            logger.info("Trial expiry warning sent to %s", user.email)
