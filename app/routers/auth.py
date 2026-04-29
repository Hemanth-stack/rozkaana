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
    phone: str
    name: str | None = None
    wa_phone: str | None = None


@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp_endpoint(
    request: SendOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    session_id, dev_otp = await send_otp(request.phone, db, redis)
    return SendOTPResponse(session_id=session_id, dev_otp=dev_otp)


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp_endpoint(
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    is_new, user = await verify_otp(request.phone, request.otp, request.session_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP verification failed")

    data = {"sub": str(user.id)}
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        is_new_user=is_new,
    )


@router.post("/dev-login", response_model=TokenResponse, tags=["dev"])
async def dev_login(
    request: DevLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Dev-only: skip OTP, get a token instantly. Disabled when MSG91 is configured."""
    from app.services.otp_service import _msg91_configured
    if _msg91_configured():
        raise HTTPException(status_code=403, detail="Dev login disabled in production")

    from app.models.user import User
    result = await db.execute(select(User).where(User.phone == request.phone))
    user = result.scalar_one_or_none()
    is_new = user is None
    if is_new:
        user = User(
            phone=request.phone,
            name=request.name,
            wa_phone=request.wa_phone or request.phone,
            wa_opted_in=bool(request.wa_phone),
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
        if request.wa_phone and not user.wa_phone:
            user.wa_phone = request.wa_phone
            user.wa_opted_in = True
        await db.flush()
        await db.refresh(user)

    # Ensure onboarding + trial exist for dev users
    if not user.onboarding_complete:
        user.onboarding_complete = True
        await db.flush()

    from app.models.subscription import Subscription
    from app.services.subscription_service import create_trial
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
    new_access = create_access_token({"sub": payload["sub"]})
    return RefreshResponse(access_token=new_access)
