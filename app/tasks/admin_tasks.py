"""
Admin one-off tasks — not scheduled, triggered manually from the admin panel or CLI.
"""
import logging
from contextlib import contextmanager

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


@celery_app.task(bind=True)
def recalculate_all_macro_targets(self):
    """
    Bulk recalculate macro targets for all active users using the updated
    ICMR weight-based protein formula. Run once after deploying the macro_scorer rewrite.

    Existing stored values used protein_pct=0.25 (~125g for a 2000 kcal plan).
    The new formula uses weight_kg × g_per_kg (ICMR: 0.8–1.4g/kg by activity level),
    producing realistic targets (e.g. 48g for a sedentary 60kg person).
    """
    from app.models.user import User
    from app.models.subscription import Subscription
    from app.services.macro_scorer import calculate_targets
    from app.tasks.menu_tasks import generate_single_menu
    from sqlalchemy import select

    updated = 0
    skipped = 0
    errors = 0

    with get_sync_session() as db:
        # Only recalculate users with complete profiles (need weight, height, age to compute)
        users = db.execute(
            select(User).where(
                User.is_active == True,  # noqa: E712
                User.weight_kg.isnot(None),
                User.height_cm.isnot(None),
                User.age.isnot(None),
            )
        ).scalars().all()

        logger.info("recalculate_all_macro_targets: found %d eligible users", len(users))

        for user in users:
            try:
                cuisine_pref = (user.cuisine_prefs or [None])[0]
                targets = calculate_targets(user, cuisine_pref=cuisine_pref)

                user.daily_calorie_target = targets["daily_calorie_target"]
                user.daily_protein_target_g = targets["daily_protein_target_g"]
                user.daily_carbs_target_g = targets["daily_carbs_target_g"]
                user.daily_fat_target_g = targets["daily_fat_target_g"]
                updated += 1

            except Exception as exc:
                logger.error("Failed to recalculate targets for user %s: %s", user.id, exc)
                errors += 1

        db.commit()

    logger.info(
        "recalculate_all_macro_targets complete: updated=%d skipped=%d errors=%d",
        updated, skipped, errors,
    )

    # Trigger menu regeneration for all active subscriptions so users immediately
    # get menus aligned to their corrected macro targets.
    _trigger_menu_regen_for_active_subscriptions()

    return {"updated": updated, "skipped": skipped, "errors": errors}


def _trigger_menu_regen_for_active_subscriptions():
    """Queue menu regeneration for all active subscribed users/households."""
    from app.models.subscription import Subscription
    from app.models.user import User
    from app.tasks.menu_tasks import generate_single_menu
    from sqlalchemy import select
    from datetime import date

    queued = 0
    with get_sync_session() as db:
        active_subs = db.execute(
            select(Subscription).where(Subscription.status.in_(["active", "trial"]))
        ).scalars().all()

        today = str(date.today())
        for sub in active_subs:
            user = db.get(User, sub.user_id)
            if not user or not user.is_active:
                continue
            try:
                if user.household_id and user.is_household_head:
                    generate_single_menu.delay(str(user.household_id), "household", today)
                elif not user.household_id:
                    generate_single_menu.delay(str(user.id), "user", today)
                queued += 1
            except Exception as exc:
                logger.error("Failed to queue regen for user %s: %s", user.id, exc)

    logger.info("Queued menu regeneration for %d subscriptions", queued)
