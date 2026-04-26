import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.otp_session import OTPSession
from app.models.user import User

_OTP_EXPIRY_MINUTES = 10
_MAX_ATTEMPTS = 5


async def send_otp(phone: str, db: AsyncSession) -> str:
    session_id = uuid.uuid4()
    otp = str(random.randint(100000, 999999))
    otp_hash = bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()
    expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=_OTP_EXPIRY_MINUTES)

    otp_session = OTPSession(
        id=session_id,
        phone=phone,
        otp_hash=otp_hash,
        expires_at=expires_at,
        attempts=0,
        is_used=False,
    )
    db.add(otp_session)
    await db.commit()

    # TODO: deliver via MSG91 SMS template in production
    print(f"[DEV OTP] phone={phone} otp={otp}")  # noqa: T201
    return str(session_id)


async def verify_otp(
    phone: str, otp: str, session_id: str, db: AsyncSession
) -> Tuple[bool, Optional[User]]:
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        return False, None

    result = await db.execute(
        select(OTPSession).where(
            OTPSession.id == sid,
            OTPSession.phone == phone,
            OTPSession.is_used == False,  # noqa: E712
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        return False, None
    if session.expires_at and datetime.now(tz=timezone.utc) > session.expires_at:
        return False, None
    if (session.attempts or 0) >= _MAX_ATTEMPTS:
        return False, None

    if not bcrypt.checkpw(otp.encode(), session.otp_hash.encode()):
        session.attempts = (session.attempts or 0) + 1
        await db.commit()
        return False, None

    session.is_used = True
    await db.commit()

    user_result = await db.execute(select(User).where(User.phone == phone))
    user = user_result.scalar_one_or_none()
    if not user:
        user = User(
            phone=phone,
            name="",
            wa_opted_in=False,
            onboarding_complete=False,
            is_admin=False,
            is_household_head=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return True, user
