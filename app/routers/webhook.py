import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.whatsapp_service import wa_service
from app.utils.redis_client import get_redis, wa_msg_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/wati", status_code=200)
async def wati_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    signature = (
        request.headers.get("X-Wati-Secret")
        or request.headers.get("x-wati-secret")
        or ""
    )
    if settings.WATI_WEBHOOK_SECRET and signature != settings.WATI_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook signature")

    payload = await request.json()
    event_type = payload.get("eventType", "")
    is_from_me = payload.get("isFromMe", True)

    if event_type == "message" and not is_from_me:
        msg_id = payload.get("id", "")
        if msg_id:
            key = wa_msg_key(msg_id)
            already = await redis.set(key, "1", ex=86400, nx=True)
            if not already:
                return {"status": "already_processed"}

        phone = payload.get("waId", "")
        text = payload.get("text", "").strip()

        if not phone:
            return {"status": "ok"}

        result = await db.execute(select(User).where(User.wa_phone == phone))
        user = result.scalar_one_or_none()
        if not user:
            return {"status": "unknown_user"}

        await _handle_command(text, user, db, redis)

    return {"status": "ok"}


async def _handle_command(text: str, user: User, db: AsyncSession, redis: Redis) -> None:
    lower = text.lower().strip()
    phone = user.wa_phone or ""

    if any(k in lower for k in ("regenerate", "regen")):
        owner_id = str(user.household_id or user.id)
        owner_type = "household" if user.household_id else "user"
        from app.tasks.menu_tasks import generate_single_menu
        generate_single_menu.delay(owner_id, owner_type, str(date.today()), None)
        await wa_service.send_text(phone, "Your menu is being regenerated. You'll receive it shortly.")

    elif lower.startswith("skip "):
        slot = lower.replace("skip ", "").strip()
        await wa_service.send_text(phone, f"Slot skip for '{slot}' noted. Use the app for full slot management.")

    elif lower.startswith("today "):
        cuisine = lower.replace("today", "").strip()
        if cuisine:
            key = f"cuisine_override:{user.household_id or user.id}:{date.today()}"
            await redis.set(key, cuisine, ex=86400)
            owner_id = str(user.household_id or user.id)
            owner_type = "household" if user.household_id else "user"
            from app.tasks.menu_tasks import generate_single_menu
            generate_single_menu.delay(owner_id, owner_type, str(date.today()), cuisine)
            await wa_service.send_text(phone, f"Generating today's menu with {cuisine} preference!")
        else:
            await _send_help(phone)

    elif lower == "pause":
        await wa_service.send_text(phone, "To pause your subscription, please visit the app: subscription > pause.")

    elif lower == "resume":
        await wa_service.send_text(phone, "To resume your subscription, please visit the app: subscription > resume.")

    elif lower in ("help", "?", "hi", "hello"):
        await _send_help(phone)

    else:
        await _send_help(phone)


async def _send_help(phone: str) -> None:
    help_text = (
        "Hello! Here are the commands I understand:\n\n"
        "• *regenerate* — Get a new menu for today\n"
        "• *today north indian* — Change today's cuisine\n"
        "• *today south indian* — Change to South Indian\n"
        "• *today chinese* — Change to Chinese\n"
        "• *skip lunch* — Note a meal skip\n"
        "• *pause* — Info on pausing subscription\n"
        "• *help* — Show this message"
    )
    await wa_service.send_text(phone, help_text)
