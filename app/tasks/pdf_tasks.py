from app.tasks.celery_app import app
from app.database import get_sync_db
from app.models.daily_menu import DailyMenu
from app.models.recipe import Recipe
from app.models.user import User
from app.models.household import Household
from app.services.pdf_service import render_menu_pdf
from app.utils.minio_client import minio_client
from datetime import date
from io import BytesIO

@app.task
def build_all_pdfs():
    today = date.today()
    with get_sync_db() as db:
        menus = db.query(DailyMenu).filter(
            DailyMenu.menu_date == today,
            DailyMenu.pdf_key == None   # not yet built
        ).all()
        for menu in menus:
            build_single_pdf.delay(str(menu.id))

@app.task(bind=True, max_retries=3)
def build_single_pdf(self, menu_id: str):
    try:
        with get_sync_db() as db:
            menu = db.query(DailyMenu).get(menu_id)
            recipe_ids = [
                menu.breakfast_id,
                menu.morning_snack_id,
                menu.lunch_id,
                menu.evening_snack_id,
                menu.dinner_id,
            ]
            recipes = {
                f"breakfast_id": None,
                f"morning_snack_id": None,
                f"lunch_id": None,
                f"evening_snack_id": None,
                f"dinner_id": None,
            }
            valid_recipe_ids = [rid for rid in recipe_ids if rid is not None]
            if valid_recipe_ids:
                recipe_objects = db.query(Recipe).filter(Recipe.id.in_(valid_recipe_ids)).all()
                recipe_map = {str(r.id): r for r in recipe_objects}
                recipes = {
                    "breakfast_id": recipe_map.get(str(menu.breakfast_id)),
                    "morning_snack_id": recipe_map.get(str(menu.morning_snack_id)),
                    "lunch_id": recipe_map.get(str(menu.lunch_id)),
                    "evening_snack_id": recipe_map.get(str(menu.evening_snack_id)),
                    "dinner_id": recipe_map.get(str(menu.dinner_id)),
                }

            members = []
            if menu.owner_type == "household":
                household = db.query(Household).get(menu.owner_id)
                members = db.query(User).filter(User.household_id == household.id).all()
            else:
                members = [db.query(User).get(menu.owner_id)]

            pdf_bytes = render_menu_pdf(menu, members, recipes)
            key = f"pdfs/{menu.menu_date}/{menu.owner_id}.pdf"
            minio_client.put_object("rozkaana-pdfs", key, BytesIO(pdf_bytes), length=len(pdf_bytes), content_type="application/pdf")
            menu.pdf_key = key
            db.commit()
    except Exception as exc:
        raise self.retry(exc=exc)