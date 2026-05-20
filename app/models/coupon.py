import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey,
    Integer, String, text, UUID,
)
from sqlalchemy.dialects.postgresql import ARRAY

from app.database import Base


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    code = Column(String(30), unique=True, nullable=False)
    description = Column(String(200), nullable=True)

    # "percent_off" → discount_value is 1–100
    # "free_days"   → discount_value is number of extra free days
    discount_type = Column(String(20), nullable=False)
    discount_value = Column(Integer, nullable=False)

    # null = applies to all plans
    applicable_plans = Column(ARRAY(String), nullable=True)

    max_redemptions = Column(Integer, nullable=True)   # null = unlimited
    redeemed_count = Column(Integer, default=0, server_default="0", nullable=False)

    valid_from = Column(Date, nullable=True)
    valid_until = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, server_default="true", nullable=False)

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    coupon_id = Column(UUID(as_uuid=True), ForeignKey("coupons.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    plan_type = Column(String(20), nullable=False)
    redeemed_at = Column(DateTime(timezone=True), server_default=text("now()"))
