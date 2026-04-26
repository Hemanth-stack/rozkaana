from sqlalchemy import Column, String, SmallInteger, DateTime, text, Date, UUID, ForeignKey
from app.database import Base
import uuid

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    plan_type = Column(String(20))
    status = Column(String(20))
    trial_start = Column(Date)
    trial_end = Column(Date)
    current_period_start = Column(Date)
    current_period_end = Column(Date)
    rzp_subscription_id = Column(String(50))
    rzp_customer_id = Column(String(50))
    paused_at = Column(Date)
    pause_days_used = Column(SmallInteger)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))