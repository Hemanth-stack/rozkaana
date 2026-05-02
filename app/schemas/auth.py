import re
from pydantic import BaseModel, field_validator, EmailStr


class SendOTPRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Enter a valid email address")
        return v


class SendOTPResponse(BaseModel):
    session_id: str
    message: str = "OTP sent to your email"
    dev_otp: str | None = None


class VerifyOTPRequest(BaseModel):
    email: str
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
