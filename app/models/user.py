from sqlalchemy import Column, String, SmallInteger, Numeric, Boolean, DateTime, text, UUID, ARRAY, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    phone = Column(String(15), unique=True, index=True)
    name = Column(String(100))
    age = Column(SmallInteger)
    gender = Column(String(10))
    weight_kg = Column(Numeric(5,2))
    height_cm = Column(Numeric(5,2))
    bmi = Column(Numeric(4,2))
    bmi_band = Column(String(20))
    goal = Column(String(20))
    eating_mode = Column(String(20))
    nv_days = Column(ARRAY(String))
    health_tags = Column(ARRAY(String))
    allergy_tags = Column(ARRAY(String))
    cuisine_prefs = Column(ARRAY(String))
    daily_calorie_target = Column(SmallInteger)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=True)
    is_household_head = Column(Boolean)
    wa_phone = Column(String(15))
    wa_opted_in = Column(Boolean)
    timezone = Column(String(50), server_default="Asia/Kolkata")
    onboarding_complete = Column(Boolean, server_default="false")
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"))

    __table_args__ = (
        Index('ix_users_health_tags', 'health_tags', postgresql_using='gin'),
        Index('ix_users_allergy_tags', 'allergy_tags', postgresql_using='gin'),
    )