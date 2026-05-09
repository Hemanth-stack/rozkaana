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
        "app.tasks.email_tasks",
        "app.tasks.seed_tasks",
        "app.tasks.signal_tasks",
    ],
)

celery_app.conf.enable_utc = True
# Timezone intentionally left as UTC (default) — all schedule hours below are UTC.
# MENU_GEN_HOUR_UTC=18 → 23:30 IST, PDF_BUILD_HOUR_UTC=22 → 03:30 IST, EMAIL_SEND_HOUR_UTC=0 → 05:30 IST
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
    "send-menu-emails": {
        "task": "app.tasks.email_tasks.send_all_emails",
        "schedule": crontab(hour=settings.EMAIL_SEND_HOUR_UTC, minute=0),
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
        "task": "app.tasks.email_tasks.send_trial_expiry_warnings",
        "schedule": crontab(hour=4, minute=30),
    },
    # Every ~3 days (Sun/Wed/Sat IST = Mon/Thu/Sun UTC at 04:30 UTC = 10:00 IST)
    "signal-prompt-users": {
        "task": "app.tasks.signal_tasks.prompt_users_for_signals",
        "schedule": crontab(hour=4, minute=30, day_of_week="0,3,6"),
    },
    # 4h after prompt on the same days — gives users time to log before analysis runs
    "signal-analyze-users": {
        "task": "app.tasks.signal_tasks.analyze_all_users_signals",
        "schedule": crontab(hour=8, minute=30, day_of_week="0,3,6"),
    },
}

app = celery_app
