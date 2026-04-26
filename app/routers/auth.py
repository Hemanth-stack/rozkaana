from fastapi import APIRouter, Depends, HTTPException
from app.schemas.auth import SendOTPRequest, SendOTPResponse, VerifyOTPRequest, VerifyOTPResponse, RefreshRequest, RefreshResponse
from app.services.otp import send_otp, verify_otp
from app.utils.jwt import create_access_token
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.user import User
import uuid

router = APIRouter()

@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp_endpoint(request: SendOTPRequest, db: AsyncSession = Depends(get_db)):
    session_id = await send_otp(request.phone, db)
    return SendOTPResponse(session_id=session_id)

@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp_endpoint(request: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    is_valid, user = await verify_otp(request.phone, request.otp, request.session_id, db)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    access_token = create_access_token({"sub": str(user.id)})
    is_new_user = user.created_at == user.updated_at  # rough check
    return VerifyOTPResponse(access_token=access_token, is_new_user=is_new_user)

@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(request: RefreshRequest):
    # Implement refresh logic
    pass