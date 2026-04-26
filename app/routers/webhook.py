from datetime import date, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.services.whatsapp_service import wa_service
from app.utils.redis_client import redis_client
from app.config import settings
from app.tasks.menu_tasks import generate_single_menu

router = APIRouter()

@router.post("/wati")
async def wati_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    signature = request.headers.get("x-wati-signature") or request.headers.get("X-WATI-SIGNATURE")
    if settings.wati_webhook_secret and signature != settings.wati_webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook signature")

    payload = await request.json()
    event_type = payload.get("eventType")

    if event_type == "message" and payload.get("isFromMe") is False:
        msg_id = payload.get("id")
        if not msg_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing message id")

        if not redis_client.set(f"wa_msg:{msg_id}", "1", ex=86400, nx=True):
            return {"status": "already_processed"}

        phone = payload.get("waId")
        text = payload.get("text", "").lower().strip()
        if not phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing sender phone")

        result = await db.execute(select(User).where(User.wa_phone == phone))
        user = result.scalar_one_or_none()
        if not user:
            return {"status": "unknown_user"}

        await _handle_command(text, user, db)

    elif event_type == "template_button_reply":
        # Future support for quick reply buttons
        pass

    return {"status": "ok"}

async def _handle_command(text: str, user: User, db: AsyncSession):
    cmd_map = {
        "regenerate": _cmd_regenerate,
        "regen": _cmd_regenerate,
        "skip lunch": _cmd_skip_slot,
        "skip breakfast": _cmd_skip_slot,
        "today chinese": _cmd_cuisine_override,
        "today italian": _cmd_cuisine_override,
        "today south indian": _cmd_cuisine_override,
        "pause": _cmd_pause_subscription,
        "help": _cmd_send_help,
    }

    for keyword, handler in cmd_map.items():
        if keyword in text:
            await handler(text, user, db)
            return

    await _cmd_send_help(text, user, db)

async def _cmd_regenerate(text: str, user: User, db: AsyncSession):
    owner_id = str(user.household_id or user.id)
    owner_type = "household" if user.household_id else "user"
    generate_single_menu.delay(owner_id, owner_type, str(date.today()))
    wa_service.send_text(user.wa_phone, "Your menu regeneration request is queued. You will receive the updated plan shortly.")

async def _cmd_skip_slot(text: str, user: User, db: AsyncSession):
    wa_service.send_text(user.wa_phone, "Slot skip commands are not supported yet. Please use the app to adjust your plan.")

async def _cmd_cuisine_override(text: str, user: User, db: AsyncSession):
    cuisine = text.replace("today", "").strip()
    if cuisine:
        key = f"wa_cuisine_override:{user.id}:{date.today()}"
        redis_client.set(key, cuisine, ex=86400)
        wa_service.send_text(user.wa_phone, f"Cuisine override for today set to {cuisine}. Your next menu will prefer this cuisine.")
    else:
        await _cmd_send_help(text, user, db)

async def _cmd_pause_subscription(text: str, user: User, db: AsyncSession):
    wa_service.send_text(user.wa_phone, "Pause subscription is not available via WhatsApp yet. Please use the app or billing page.")

async def _cmd_send_help(text: str, user: User, db: AsyncSession):
    help_text = (
        "Hi! You can use the following commands:\n"
        "regenerate\n"
        "today chinese\n"
        "today italian\n"
        "pause\n"
        "help"
    )
    wa_service.send_text(user.wa_phone, help_text)
