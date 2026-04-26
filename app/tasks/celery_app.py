from celery import Celery
from celery.schedules import crontab
from app.config import settings

app = Celery(
    "rozkaana",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.menu_tasks", "app.tasks.pdf_tasks", "app.tasks.wa_tasks"]
)
app.conf.timezone = "Asia/Kolkata"
app.conf.beat_schedule = {
    # Midnight: generate all menus
    "generate-daily-menus": {
        "task": "app.tasks.menu_tasks.generate_all_menus",
        "schedule": crontab(hour=0, minute=0),
    },
    # 4 AM: build PDFs (menus are ready by then)
    "build-daily-pdfs": {
        "task": "app.tasks.pdf_tasks.build_all_pdfs",
        "schedule": crontab(hour=4, minute=0),
    },
    # 6 AM: send WhatsApp messages
    "send-whatsapp": {
        "task": "app.tasks.wa_tasks.send_all_whatsapp",
        "schedule": crontab(hour=6, minute=0),
    },
    # Hourly: clean expired OTP sessions
    "clean-otps": {
        "task": "app.tasks.menu_tasks.clean_expired_otps",
        "schedule": crontab(minute=0),
    },
    # Daily 1AM: expire cancelled subscriptions
    "expire-subscriptions": {
        "task": "app.tasks.menu_tasks.expire_subscriptions",
        "schedule": crontab(hour=1, minute=0),
    },
}