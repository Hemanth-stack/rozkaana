import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, SmallInteger, String, text, UUID

from app.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    plan_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="trial")
    trial_start = Column(Date, nullable=True)
    trial_end = Column(Date, nullable=True)
    current_period_start = Column(Date, nullable=True)
    current_period_end = Column(Date, nullable=True)
    rzp_subscription_id = Column(String(50), nullable=True)
    rzp_customer_id = Column(String(50), nullable=True)
    rzp_plan_id = Column(String(50), nullable=True)
    paused_at = Column(Date, nullable=True)
    pause_days_used = Column(SmallInteger, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"))
