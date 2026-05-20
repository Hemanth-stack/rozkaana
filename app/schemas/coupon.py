from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class CouponCreate(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str   # "percent_off" | "free_days"
    discount_value: int
    applicable_plans: Optional[list[str]] = None  # None = all plans
    max_redemptions: Optional[int] = None          # None = unlimited
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("discount_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("percent_off", "free_days"):
            raise ValueError("discount_type must be 'percent_off' or 'free_days'")
        return v

    @field_validator("discount_value")
    @classmethod
    def validate_value(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("discount_value must be positive")
        return v


class CouponOut(BaseModel):
    id: UUID
    code: str
    description: Optional[str]
    discount_type: str
    discount_value: int
    applicable_plans: Optional[list[str]]
    max_redemptions: Optional[int]
    redeemed_count: int
    valid_from: Optional[date]
    valid_until: Optional[date]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CouponToggle(BaseModel):
    is_active: bool


class CouponListResponse(BaseModel):
    coupons: list[CouponOut]
    total: int


# ── User-facing ───────────────────────────────────────────────────────────────

class ValidateCouponRequest(BaseModel):
    code: str
    plan_type: str

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, v: str) -> str:
        return v.strip().upper()


class ValidateCouponResponse(BaseModel):
    valid: bool
    discount_type: str          # "percent_off" | "free_days"
    discount_value: int
    original_amount: int        # paise (0 for free_days)
    discounted_amount: int      # paise (0 for free_days)
    free_days: int              # 0 for percent_off
    message: str
