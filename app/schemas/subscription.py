from pydantic import BaseModel
from typing import Optional

class SubscriptionResponse(BaseModel):
    id: str
    plan_type: str
    status: str
    trial_start: Optional[str]
    trial_end: Optional[str]
    current_period_start: Optional[str]
    current_period_end: Optional[str]
    paused_at: Optional[str]
    pause_days_used: int

class UpgradeRequest(BaseModel):
    plan_type: str

class UpgradeResponse(BaseModel):
    payment_link: str

class PauseResponse(BaseModel):
    message: str

class ResumeResponse(BaseModel):
    message: str

class CancelResponse(BaseModel):
    message: str