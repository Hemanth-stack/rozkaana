from sqlalchemy import Column, String, SmallInteger, Numeric, Boolean, DateTime, text, UUID, ARRAY, Index
from sqlalchemy.dialects.postgresql import JSONB, TEXT
from app.database import Base
import uuid

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    name = Column(String(200))
    name_local = Column(String(200))
    meal_type = Column(String(20), index=True)
    cuisine_region = Column(String(30), index=True)
    eating_mode_tags = Column(ARRAY(String))
    health_safe_tags = Column(ARRAY(String))
    allergy_free_tags = Column(ARRAY(String))
    calories = Column(SmallInteger)
    protein_g = Column(Numeric(5,2))
    carbs_g = Column(Numeric(5,2))
    fat_g = Column(Numeric(5,2))
    fibre_g = Column(Numeric(5,2))
    serving_unit = Column(String(30))
    prep_time_mins = Column(SmallInteger)
    spice_level = Column(String(10))
    main_ingredient = Column(String(50))
    ingredients = Column(JSONB)
    steps = Column(ARRAY(TEXT))
    is_verified = Column(Boolean, index=True)
    is_active = Column(Boolean)
    source = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index('ix_recipes_eating_mode_tags', 'eating_mode_tags', postgresql_using='gin'),
        Index('ix_recipes_health_safe_tags', 'health_safe_tags', postgresql_using='gin'),
        Index('ix_recipes_allergy_free_tags', 'allergy_free_tags', postgresql_using='gin'),
    )