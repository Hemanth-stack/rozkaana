import re
from pydantic import BaseModel, field_validator


class SendOTPRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\+91[6-9]\d{9}$", v):
            raise ValueError("Phone must be E.164 Indian format: +91XXXXXXXXXX")
        return v


class SendOTPResponse(BaseModel):
    session_id: str
    message: str = "OTP sent successfully"


class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str
    session_id: str

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        if not re.match(r"^\d{6}$", v):
            raise ValueError("OTP must be 6 digits")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
