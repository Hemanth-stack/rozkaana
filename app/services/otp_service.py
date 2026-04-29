import random
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.otp_session import OTPSession
from app.models.user import User
from app.utils.security import hash_otp, verify_otp_hash

_OTP_EXPIRY_MINUTES = 10
_MAX_ATTEMPTS = 3
_MAX_OTP_PER_HOUR = 5

import logging
logger = logging.getLogger(__name__)

def _msg91_configured() -> bool:
    key = settings.MSG91_AUTH_KEY.strip()
    # Treat any obviously-fake value as unconfigured
    return bool(key) and not any(p in key.lower() for p in (
        "placeholder", "your_", "your-", "xxxx", "changeme", "msg91-auth"
    ))


async def send_otp(phone: str, db: AsyncSession, redis: Redis) -> tuple[str, str | None]:
    rate_key = f"otp_rate:{phone}"
    count = await redis.get(rate_key)
    if count and int(count) >= _MAX_OTP_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Try again in an hour.",
        )

    otp = str(random.randint(100000, 999999))
    otp_hash = hash_otp(otp)
    session_id = uuid.uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_OTP_EXPIRY_MINUTES)

    otp_session = OTPSession(
        id=session_id,
        phone=phone,
        otp_hash=otp_hash,
        expires_at=expires_at,
        attempts=0,
        is_used=False,
    )
    db.add(otp_session)
    await db.flush()

    dev_otp: str | None = None
    if _msg91_configured():
        await _send_sms_msg91(phone, otp)
    else:
        logger.warning("MSG91 not configured — OTP for %s: %s", phone, otp)
        dev_otp = otp  # return to caller so it can surface in response

    pipe = redis.pipeline()
    await pipe.incr(rate_key)
    await pipe.expire(rate_key, 3600)
    await pipe.execute()

    return str(session_id), dev_otp


async def verify_otp(phone: str, otp: str, session_id: str, db: AsyncSession) -> tuple[bool, User | None]:
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session_id")

    result = await db.execute(
        select(OTPSession).where(
            OTPSession.id == sid,
            OTPSession.phone == phone,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP session not found")
    if session.is_used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP already used")
    if datetime.now(timezone.utc) > session.expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired")
    if (session.attempts or 0) >= _MAX_ATTEMPTS:
        session.is_used = True
        await db.flush()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many failed attempts")

    if not verify_otp_hash(otp, session.otp_hash):
        session.attempts = (session.attempts or 0) + 1
        if session.attempts >= _MAX_ATTEMPTS:
            session.is_used = True
        await db.flush()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

    session.is_used = True
    await db.flush()

    user_result = await db.execute(select(User).where(User.phone == phone))
    user = user_result.scalar_one_or_none()

    is_new = user is None
    if is_new:
        user = User(
            phone=phone,
            wa_opted_in=False,
            onboarding_complete=False,
            is_admin=False,
            is_household_head=False,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

    return is_new, user


async def _send_sms_msg91(phone: str, otp: str) -> None:
    # MSG91 v5 — authkey goes in header, mobile must be without +
    mobile = phone.lstrip("+")
    headers = {
        "authkey": settings.MSG91_AUTH_KEY,
        "accept": "application/json",
        "content-type": "application/json",
    }
    payload = {
        "template_id": settings.MSG91_TEMPLATE_ID,
        "mobile": mobile,
        "otp": otp,
        "sender": settings.MSG91_SENDER_ID,
        "otp_length": 6,
        "otp_expiry": 10,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.msg91.com/api/v5/otp",
                json=payload,
                headers=headers,
            )
            resp_text = resp.text
            if resp.status_code not in (200, 201):
                logger.warning("MSG91 error %s: %s", resp.status_code, resp_text)
            else:
                logger.info("MSG91 OTP sent to %s — response: %s", phone, resp_text)
    except Exception as exc:
        logger.warning("MSG91 send failed: %s", exc)
