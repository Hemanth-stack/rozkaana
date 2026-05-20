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


class CheckoutRequest(BaseModel):
    plan_type: str
    coupon_code: Optional[str] = None


class CheckoutResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str
    user_name: str
    user_email: str
    plan_type: str
    plan_label: str
    coupon_code: Optional[str] = None
    original_amount: Optional[int] = None


class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str


class PauseResponse(BaseModel):
    message: str
    paused_at: Optional[date]


class ResumeResponse(BaseModel):
    message: str
    status: str


class CancelResponse(BaseModel):
    message: str
    status: str
