from sqlalchemy import Column, String, SmallInteger, Numeric, Boolean, DateTime, text, Date, UUID, ForeignKey, UniqueConstraint
from app.database import Base
import uuid

class DailyMenu(Base):
    __tablename__ = "daily_menus"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    owner_id = Column(UUID(as_uuid=True), index=True)
    owner_type = Column(String(10))
    menu_date = Column(Date, index=True)
    breakfast_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"))
    morning_snack_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"))
    lunch_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"))
    evening_snack_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"))
    dinner_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"))
    total_calories = Column(SmallInteger)
    total_protein_g = Column(Numeric(5,2))
    cuisine_override = Column(String(30))
    is_regenerated = Column(Boolean)
    pdf_key = Column(String(300))
    pdf_url = Column(String)
    wa_sent_at = Column(DateTime(timezone=True))
    wa_status = Column(String(20))
    generated_at = Column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint('owner_id', 'owner_type', 'menu_date'),
    )