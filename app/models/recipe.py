import uuid

from sqlalchemy import (
    ARRAY, Boolean, Column, DateTime, Index,
    Numeric, SmallInteger, String, text, UUID,
)
from sqlalchemy.dialects.postgresql import JSONB, TEXT

from app.database import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    name = Column(String(200), nullable=False)
    name_local = Column(String(200), nullable=True)
    meal_type = Column(String(20), nullable=False, index=True)
    cuisine_region = Column(String(30), nullable=False, index=True)
    eating_mode_tags = Column(ARRAY(String), nullable=False, server_default=text("'{}'::varchar[]"))
    health_safe_tags = Column(ARRAY(String), nullable=True)
    allergy_free_tags = Column(ARRAY(String), nullable=True)
    calories = Column(SmallInteger, nullable=False)
    protein_g = Column(Numeric(5, 2), nullable=False)
    carbs_g = Column(Numeric(5, 2), nullable=False)
    fat_g = Column(Numeric(5, 2), nullable=False)
    fibre_g = Column(Numeric(5, 2), nullable=True)
    sugar_g = Column(Numeric(5, 2), nullable=True)
    # India-critical micronutrients — used for health-condition filtering
    sodium_mg = Column(Numeric(7, 1), nullable=True)        # hypertension: keep <600mg/meal
    potassium_mg = Column(Numeric(7, 1), nullable=True)     # hypertension: target high
    iron_mg = Column(Numeric(6, 2), nullable=True)          # anemia / women
    calcium_mg = Column(Numeric(7, 1), nullable=True)       # osteoporosis / dairy-free
    vitamin_c_mg = Column(Numeric(6, 2), nullable=True)     # boosts iron absorption
    vitamin_b12_mcg = Column(Numeric(5, 2), nullable=True)  # vegetarian deficiency risk
    vitamin_d_mcg = Column(Numeric(5, 2), nullable=True)    # India deficiency epidemic
    glycemic_index = Column(SmallInteger, nullable=True)    # diabetes / PCOS (0-100)
    serving_unit = Column(String(200), nullable=True)
    prep_time_mins = Column(SmallInteger, nullable=True)
    spice_level = Column(String(20), nullable=True)
    main_ingredient = Column(String(100), nullable=True)
    ingredients = Column(JSONB, nullable=True)
    steps = Column(ARRAY(TEXT), nullable=True)
    is_verified = Column(Boolean, default=False, server_default="false", index=True)
    is_active = Column(Boolean, default=True, server_default="true")
    source = Column(String(20), default="manual", server_default="manual")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"))

    __table_args__ = (
        Index("ix_recipes_eating_mode_tags", "eating_mode_tags", postgresql_using="gin"),
        Index("ix_recipes_health_safe_tags", "health_safe_tags", postgresql_using="gin"),
        Index("ix_recipes_allergy_free_tags", "allergy_free_tags", postgresql_using="gin"),
    )
