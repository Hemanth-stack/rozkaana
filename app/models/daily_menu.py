import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey,
    Numeric, SmallInteger, String, text, UUID, UniqueConstraint,
)

from app.database import Base


class DailyMenu(Base):
    __tablename__ = "daily_menus"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    owner_type = Column(String(10), nullable=False)
    menu_date = Column(Date, nullable=False, index=True)
    breakfast_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=True)
    morning_snack_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=True)
    lunch_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=True)
    evening_snack_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=True)
    dinner_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=True)
    total_calories = Column(SmallInteger, nullable=True)
    total_protein_g = Column(Numeric(5, 2), nullable=True)
    total_carbs_g = Column(Numeric(5, 2), nullable=True)
    total_fat_g = Column(Numeric(5, 2), nullable=True)
    cuisine_override = Column(String(30), nullable=True)
    is_regenerated = Column(Boolean, default=False, server_default="false")
    pdf_key = Column(String(300), nullable=True)
    pdf_url = Column(String, nullable=True)
    wa_sent_at = Column(DateTime(timezone=True), nullable=True)
    wa_status = Column(String(20), default="pending", server_default="pending")
    generated_at = Column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("owner_id", "owner_type", "menu_date", name="uq_daily_menu_owner_date"),
    )
