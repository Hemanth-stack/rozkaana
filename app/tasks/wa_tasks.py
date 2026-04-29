import logging
from contextlib import contextmanager
from datetime import date

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
    logger.info("WhatsApp sending disabled in dev mode. Use /dev chat instead.")


@celery_app.task(bind=True, max_retries=0)
def send_single_whatsapp(self, menu_id: str):
    """Dev mode: mark as skipped instead of sending."""
    import uuid as _uuid
    from app.models.daily_menu import DailyMenu
    with get_sync_session() as db:
        menu = db.query(DailyMenu).get(_uuid.UUID(menu_id))
        if menu:
            menu.wa_status = "dev_skipped"
    logger.info("WA disabled (dev mode) — menu %s marked dev_skipped", menu_id)


@celery_app.task
def send_trial_expiry_warnings():
    logger.info("Trial expiry warnings disabled in dev mode.")
