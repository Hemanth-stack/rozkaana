import uuid

from sqlalchemy import (
    ARRAY, Column, DateTime, Numeric, String, text, UniqueConstraint, UUID,
)

from app.database import Base


class IFCTIngredient(Base):
    __tablename__ = "ifct_ingredients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                server_default=text("gen_random_uuid()"))
    name = Column(String(200), nullable=False)
    aliases = Column(ARRAY(String), server_default=text("'{}'::varchar[]"))
    food_group = Column(String(50), nullable=True)

    calories_per_100g = Column(Numeric(7, 2), nullable=True)
    protein_g = Column(Numeric(6, 3), nullable=True)
    carbs_g = Column(Numeric(6, 3), nullable=True)
    fat_g = Column(Numeric(6, 3), nullable=True)
    fibre_g = Column(Numeric(6, 3), nullable=True)
    sugar_g = Column(Numeric(6, 3), nullable=True)
    sodium_mg = Column(Numeric(8, 2), nullable=True)
    potassium_mg = Column(Numeric(8, 2), nullable=True)
    iron_mg = Column(Numeric(7, 3), nullable=True)
    calcium_mg = Column(Numeric(8, 2), nullable=True)
    vitamin_c_mg = Column(Numeric(7, 3), nullable=True)
    vitamin_b12_mcg = Column(Numeric(6, 3), nullable=True)
    vitamin_d_mcg = Column(Numeric(6, 3), nullable=True)
    water_g = Column(Numeric(6, 2), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint('name', name='uq_ifct_name'),
    )
