from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    id: UUID
    user_id: UUID
    plan_type: str
    status: str
    trial_start: Optional[date]
    trial_end: Optional[date]
    current_period_start: Optional[date]
    current_period_end: Optional[date]
    rzp_subscription_id: Optional[str]
    paused_at: Optional[date]
    pause_days_used: int = 0

    model_config = {"from_attributes": True}


class UpgradeRequest(BaseModel):
    plan_type: str


class UpgradeResponse(BaseModel):
    payment_link: str
    rzp_subscription_id: str


class PauseResponse(BaseModel):
    message: str
    paused_at: Optional[date]


class ResumeResponse(BaseModel):
    message: str
    status: str


class CancelResponse(BaseModel):
    message: str
    status: str
