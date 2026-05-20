import uuid

from sqlalchemy import (
    ARRAY, Boolean, Column, DateTime, Date, ForeignKey, Index,
    Numeric, SmallInteger, String, text, UUID,
)

from app.database import Base


class HouseholdMember(Base):
    """
    Lightweight member profile managed by the household head.
    Covers children and adults who may not have their own app accounts.
    linked_user_id is set only when a registered User account is explicitly linked.
    """
    __tablename__ = "household_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                server_default=text("gen_random_uuid()"))
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    linked_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
                            nullable=True, index=True)
    name = Column(String(100), nullable=False)
    member_type = Column(String(10), nullable=False)  # adult/teen/child/infant/senior
    age = Column(SmallInteger, nullable=True)
    gender = Column(String(10), nullable=True)
    weight_kg = Column(Numeric(5, 2), nullable=True)
    height_cm = Column(Numeric(5, 2), nullable=True)
    bmi = Column(Numeric(4, 2), nullable=True)
    bmi_band = Column(String(20), nullable=True)
    eating_mode = Column(String(20), nullable=True)
    activity_level = Column(String(20), nullable=True)
    health_tags = Column(ARRAY(String), nullable=True)
    allergy_tags = Column(ARRAY(String), nullable=True)
    goal = Column(String(20), nullable=True)
    daily_calorie_target = Column(SmallInteger, nullable=True)
    daily_protein_target_g = Column(Numeric(5, 1), nullable=True)
    daily_carbs_target_g = Column(Numeric(5, 1), nullable=True)
    daily_fat_target_g = Column(Numeric(5, 1), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"))

    __table_args__ = (
        Index("ix_hm_health_tags", "health_tags", postgresql_using="gin"),
        Index("ix_hm_allergy_tags", "allergy_tags", postgresql_using="gin"),
    )
