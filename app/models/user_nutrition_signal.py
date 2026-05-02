import uuid

from sqlalchemy import (
    ARRAY, Boolean, Column, Date, DateTime,
    ForeignKey, Numeric, SmallInteger, String, text, UUID,
)

from app.database import Base


class UserNutritionSignal(Base):
    __tablename__ = "user_nutrition_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    signal_date = Column(Date, nullable=False, index=True, server_default=text("CURRENT_DATE"))

    # Energy & Satiety (1-10 scale)
    energy_level = Column(SmallInteger, nullable=True)
    hunger_rating = Column(SmallInteger, nullable=True)

    # Digestion
    digestion_comfort = Column(SmallInteger, nullable=True)

    # Sleep
    sleep_quality = Column(SmallInteger, nullable=True)
    sleep_hours = Column(Numeric(3, 1), nullable=True)

    # Mental state
    mood = Column(String(20), nullable=True)
    focus_level = Column(SmallInteger, nullable=True)

    # Metabolic / deficiency signals
    blood_sugar_dip = Column(Boolean, nullable=True)   # energy crash = insulin issue
    muscle_cramps = Column(Boolean, nullable=True)     # magnesium/potassium deficiency
    hair_loss_noticed = Column(Boolean, nullable=True) # iron/zinc/protein deficiency

    # Optional biometrics
    weight_kg = Column(Numeric(5, 2), nullable=True)
    blood_glucose_mg_dl = Column(SmallInteger, nullable=True)

    # Menu adherence
    followed_menu = Column(Boolean, nullable=True)
    skipped_slots = Column(ARRAY(String), nullable=True)
    notes = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
