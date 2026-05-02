from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.schemas.auth import (
    RefreshRequest, RefreshResponse,
    SendOTPRequest, SendOTPResponse,
    TokenResponse, VerifyOTPRequest,
)
from app.services.otp_service import send_otp, verify_otp
from app.utils.redis_client import get_redis
from app.utils.security import create_access_token, create_refresh_token, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])


class DevLoginRequest(BaseModel):
    email: str
    name: str | None = None


@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp_endpoint(
    request: SendOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    session_id, dev_otp = await send_otp(request.email, db, redis)
    return SendOTPResponse(session_id=session_id, dev_otp=dev_otp)


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp_endpoint(
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    is_new, user = await verify_otp(request.email, request.otp, request.session_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP verification failed")
    data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(data),
        refresh_token=create_refresh_token(data),
        is_new_user=is_new,
    )


@router.post("/dev-login", response_model=TokenResponse, tags=["dev"])
async def dev_login(
    request: DevLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Dev-only: skip OTP. Automatically disabled when SMTP is configured."""
    from app.services.otp_service import _smtp_configured
    if _smtp_configured():
        raise HTTPException(status_code=403, detail="Dev login disabled — use /auth/send-otp")

    from app.models.user import User
    from app.models.subscription import Subscription
    from app.services.subscription_service import create_trial

    email = request.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    is_new = user is None

    if is_new:
        import hashlib
        phone_placeholder = "e" + hashlib.md5(email.encode()).hexdigest()[:13]
        user = User(
            phone=phone_placeholder,
            email=email,
            name=request.name,
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
        if request.name and not user.name:
            user.name = request.name
        user.email_verified = True
        await db.flush()
        await db.refresh(user)

    # Ensure onboarding + trial
    if not user.onboarding_complete:
        user.onboarding_complete = True
        await db.flush()

    sub = (await db.execute(select(Subscription).where(Subscription.user_id == user.id))).scalar_one_or_none()
    if not sub:
        await create_trial(user.id, "solo_pro", db)

    data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(data),
        refresh_token=create_refresh_token(data),
        is_new_user=is_new,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token_endpoint(request: RefreshRequest):
    payload = decode_token(request.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return RefreshResponse(access_token=create_access_token({"sub": payload["sub"]}))
