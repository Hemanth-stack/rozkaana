import uuid

from sqlalchemy import (
    ARRAY, Boolean, Column, DateTime, ForeignKey, Index,
    Numeric, SmallInteger, String, text, UUID,
)

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    phone = Column(String(15), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    age = Column(SmallInteger, nullable=True)
    gender = Column(String(10), nullable=True)
    weight_kg = Column(Numeric(5, 2), nullable=True)
    height_cm = Column(Numeric(5, 2), nullable=True)
    bmi = Column(Numeric(4, 2), nullable=True)
    bmi_band = Column(String(20), nullable=True)
    goal = Column(String(20), nullable=True)
    eating_mode = Column(String(20), nullable=True)
    nv_days = Column(ARRAY(String), nullable=True)
    health_tags = Column(ARRAY(String), nullable=True)
    allergy_tags = Column(ARRAY(String), nullable=True)
    cuisine_prefs = Column(ARRAY(String), nullable=True)
    daily_calorie_target = Column(SmallInteger, nullable=True)
    daily_protein_target_g = Column(Numeric(5, 1), nullable=True)
    daily_carbs_target_g = Column(Numeric(5, 1), nullable=True)
    daily_fat_target_g = Column(Numeric(5, 1), nullable=True)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=True)
    is_household_head = Column(Boolean, default=False, server_default="false")
    wa_phone = Column(String(15), nullable=True)
    wa_opted_in = Column(Boolean, default=False, server_default="false")
    onboarding_complete = Column(Boolean, default=False, server_default="false")
    is_admin = Column(Boolean, default=False, server_default="false")
    is_active = Column(Boolean, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"))

    __table_args__ = (
        Index("ix_users_health_tags", "health_tags", postgresql_using="gin"),
        Index("ix_users_allergy_tags", "allergy_tags", postgresql_using="gin"),
    )
