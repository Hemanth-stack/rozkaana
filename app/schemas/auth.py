from pydantic import BaseModel

class SendOTPRequest(BaseModel):
    phone: str

class SendOTPResponse(BaseModel):
    session_id: str

class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str
    session_id: str

class VerifyOTPResponse(BaseModel):
    access_token: str
    is_new_user: bool

class RefreshRequest(BaseModel):
    refresh_token: str

class RefreshResponse(BaseModel):
    access_token: str