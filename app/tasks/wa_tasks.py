from app.tasks.celery_app import app
from app.database import get_sync_db
from app.models.daily_menu import DailyMenu
from app.models.user import User
from app.models.household import Household
from app.services.whatsapp_service import send_meal_plan
from app.utils.minio_client import minio_client
from datetime import date, datetime, timedelta

@app.task
def send_all_whatsapp():
    today = date.today()
    with get_sync_db() as db:
        menus = db.query(DailyMenu).filter(
            DailyMenu.menu_date == today,
            DailyMenu.wa_sent_at == None,
            DailyMenu.pdf_key != None
        ).all()
        for menu in menus:
            send_single_whatsapp.delay(str(menu.id))

@app.task(bind=True, max_retries=2, default_retry_delay=300)
def send_single_whatsapp(self, menu_id: str):
    with get_sync_db() as db:
        menu = db.query(DailyMenu).get(menu_id)
        user = _get_owner_wa_details(db, menu)
        presigned_url = minio_client.presigned_get_object(
            "rozkaana-pdfs", menu.pdf_key, expires=timedelta(hours=12)
        )
        success = send_meal_plan(
            phone=user.wa_phone,
            name=user.name,
            pdf_url=presigned_url,
            date=menu.menu_date
        )
        if success:
            menu.wa_sent_at = datetime.utcnow()
            menu.wa_status = "sent"
        else:
            menu.wa_status = "failed"
            raise self.retry()
        db.commit()

def _get_owner_wa_details(db, menu: DailyMenu):
    if menu.owner_type == "user":
        return db.query(User).get(menu.owner_id)
    else:
        household = db.query(Household).get(menu.owner_id)
        return db.query(User).get(household.head_user_id)