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
def build_all_pdfs():
    from app.models.daily_menu import DailyMenu
    today = date.today()
    with get_sync_session() as db:
        menus = db.query(DailyMenu).filter(
            DailyMenu.menu_date == today,
            DailyMenu.pdf_key.is_(None),
        ).all()
        for menu in menus:
            build_single_pdf.delay(str(menu.id))
    logger.info("Queued PDF build for %d menus", len(menus))


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def build_single_pdf(self, menu_id: str):
    from app.models.daily_menu import DailyMenu
    from app.models.recipe import Recipe
    from app.models.user import User
    from app.models.household import Household
    from app.services.pdf_service import render_menu_pdf
    from app.utils.minio_client import upload_pdf
    import uuid as _uuid

    try:
        with get_sync_session() as db:
            menu = db.query(DailyMenu).get(_uuid.UUID(menu_id))
            if not menu:
                logger.error("Menu %s not found", menu_id)
                return

            recipe_ids = [
                menu.breakfast_id,
                menu.morning_snack_id,
                menu.lunch_id,
                menu.evening_snack_id,
                menu.dinner_id,
            ]
            valid_ids = [rid for rid in recipe_ids if rid is not None]
            recipe_map: dict = {}
            if valid_ids:
                recipes_q = db.query(Recipe).filter(Recipe.id.in_(valid_ids)).all()
                recipe_map = {str(r.id): r for r in recipes_q}

            recipes_by_slot = {
                "breakfast_id": recipe_map.get(str(menu.breakfast_id)) if menu.breakfast_id else None,
                "morning_snack_id": recipe_map.get(str(menu.morning_snack_id)) if menu.morning_snack_id else None,
                "lunch_id": recipe_map.get(str(menu.lunch_id)) if menu.lunch_id else None,
                "evening_snack_id": recipe_map.get(str(menu.evening_snack_id)) if menu.evening_snack_id else None,
                "dinner_id": recipe_map.get(str(menu.dinner_id)) if menu.dinner_id else None,
            }

            if menu.owner_type == "household":
                household = db.query(Household).get(menu.owner_id)
                if household:
                    members = db.query(User).filter(User.household_id == household.id).all()
                else:
                    members = []
            else:
                user = db.query(User).get(menu.owner_id)
                members = [user] if user else []

            if not members:
                logger.error("No members found for menu %s", menu_id)
                return

            pdf_bytes = render_menu_pdf(menu, members, recipes_by_slot)

            object_key = f"pdfs/{menu.menu_date}/{menu.owner_id}.pdf"
            upload_pdf(object_key, pdf_bytes)

            menu.pdf_key = object_key
            logger.info("Built PDF for menu %s → %s", menu_id, object_key)

    except Exception as exc:
        logger.error("PDF build failed for menu %s: %s", menu_id, exc)
        raise self.retry(exc=exc)
