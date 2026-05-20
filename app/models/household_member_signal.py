import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Date, ForeignKey,
    Numeric, SmallInteger, String, text, UUID, UniqueConstraint,
)

from app.database import Base


class HouseholdMemberSignal(Base):
    """Daily wellness signal for a household member (including children)."""
    __tablename__ = "household_member_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                server_default=text("gen_random_uuid()"))
    member_id = Column(UUID(as_uuid=True), ForeignKey("household_members.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    signal_date = Column(Date, nullable=False, index=True, server_default=text("CURRENT_DATE"))
    energy_level = Column(SmallInteger, nullable=True)
    hunger_rating = Column(SmallInteger, nullable=True)
    digestion_comfort = Column(SmallInteger, nullable=True)
    sleep_quality = Column(SmallInteger, nullable=True)
    sleep_hours = Column(Numeric(3, 1), nullable=True)
    mood = Column(String(20), nullable=True)
    focus_level = Column(SmallInteger, nullable=True)
    blood_sugar_dip = Column(Boolean, nullable=True)
    muscle_cramps = Column(Boolean, nullable=True)
    hair_loss_noticed = Column(Boolean, nullable=True)
    weight_kg = Column(Numeric(5, 2), nullable=True)
    blood_glucose_mg_dl = Column(SmallInteger, nullable=True)
    followed_menu = Column(Boolean, nullable=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("member_id", "signal_date", name="uq_hms_member_date"),
    )
