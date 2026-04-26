from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "rozkaana",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.menu_tasks",
        "app.tasks.pdf_tasks",
        "app.tasks.wa_tasks",
    ],
)

celery_app.conf.timezone = "Asia/Kolkata"
celery_app.conf.enable_utc = True
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

celery_app.conf.beat_schedule = {
    "generate-daily-menus": {
        "task": "app.tasks.menu_tasks.generate_all_menus",
        "schedule": crontab(hour=settings.MENU_GEN_HOUR_UTC, minute=0),
    },
    "build-daily-pdfs": {
        "task": "app.tasks.pdf_tasks.build_all_pdfs",
        "schedule": crontab(hour=settings.PDF_BUILD_HOUR_UTC, minute=0),
    },
    "send-whatsapp-messages": {
        "task": "app.tasks.wa_tasks.send_all_whatsapp",
        "schedule": crontab(hour=settings.WA_SEND_HOUR_UTC, minute=0),
    },
    "expire-subscriptions": {
        "task": "app.tasks.menu_tasks.expire_subscriptions",
        "schedule": crontab(hour=1, minute=0),
    },
    "clean-otp-sessions": {
        "task": "app.tasks.menu_tasks.clean_expired_otps",
        "schedule": crontab(minute=0),
    },
    "send-trial-expiry-warnings": {
        "task": "app.tasks.wa_tasks.send_trial_expiry_warnings",
        "schedule": crontab(hour=4, minute=30),
    },
}

# Legacy alias
app = celery_app
