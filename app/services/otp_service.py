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


async def send_otp(phone: str, db: AsyncSession, redis: Redis) -> str:
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

    await _send_sms_msg91(phone, otp)

    pipe = redis.pipeline()
    await pipe.incr(rate_key)
    await pipe.expire(rate_key, 3600)
    await pipe.execute()

    return str(session_id)


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
    e164 = phone.lstrip("+")
    payload = {
        "template_id": settings.MSG91_TEMPLATE_ID,
        "mobile": e164,
        "authkey": settings.MSG91_AUTH_KEY,
        "otp": otp,
        "sender": settings.MSG91_SENDER_ID,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post("https://api.msg91.com/api/v5/otp", json=payload)
            if resp.status_code not in (200, 201):
                import logging
                logging.warning("MSG91 returned %s: %s", resp.status_code, resp.text)
    except Exception as exc:
        import logging
        logging.warning("MSG91 send failed: %s", exc)
