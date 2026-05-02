import logging
import random
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.otp_session import OTPSession
from app.models.user import User
from app.utils.security import hash_otp, verify_otp_hash

logger = logging.getLogger(__name__)

_OTP_EXPIRY_MINUTES = 10
_MAX_ATTEMPTS = 3
_MAX_OTP_PER_HOUR = 5


def _smtp_configured() -> bool:
    return settings.SMTP_USER not in ("your@gmail.com", "", "placeholder")


async def send_otp(email: str, db: AsyncSession, redis: Redis) -> tuple[str, str | None]:
    rate_key = f"otp_rate:{email}"
    count = await redis.get(rate_key)
    if count and int(count) >= _MAX_OTP_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Try again in an hour.",
        )

    otp = str(secrets.randbelow(900000) + 100000)
    otp_hash = hash_otp(otp)
    session_id = uuid.uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_OTP_EXPIRY_MINUTES)

    otp_session = OTPSession(
        id=session_id,
        phone=email,          # reusing phone column to store email identifier
        otp_hash=otp_hash,
        expires_at=expires_at,
        attempts=0,
        is_used=False,
    )
    db.add(otp_session)
    await db.flush()

    dev_otp: str | None = None
    if _smtp_configured():
        from app.services.email_service import email_service
        # Look up user name for personalisation
        user_result = await db.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()
        name = user.name or "" if user else ""
        await email_service.send_otp(email, otp, name)
    else:
        logger.warning("SMTP not configured — OTP for %s: %s", email, otp)
        dev_otp = otp

    pipe = redis.pipeline()
    await pipe.incr(rate_key)
    await pipe.expire(rate_key, 3600)
    await pipe.execute()

    return str(session_id), dev_otp


async def verify_otp(email: str, otp: str, session_id: str, db: AsyncSession) -> tuple[bool, User | None]:
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session_id")

    result = await db.execute(
        select(OTPSession).where(
            OTPSession.id == sid,
            OTPSession.phone == email,
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

    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()

    is_new = user is None
    if is_new:
        import hashlib
        phone_placeholder = "e" + hashlib.md5(email.encode()).hexdigest()[:13]
        user = User(
            phone=phone_placeholder,
            email=email,
            email_verified=True,
            onboarding_complete=False,
            is_admin=False,
            is_household_head=False,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
    else:
        user.email_verified = True
        await db.flush()
        await db.refresh(user)

    return is_new, user
