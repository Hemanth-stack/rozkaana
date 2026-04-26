import uuid

from sqlalchemy import ARRAY, Column, DateTime, ForeignKey, SmallInteger, String, text, UUID

from app.database import Base


class Household(Base):
    __tablename__ = "households"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    name = Column(String(100), nullable=False)
    head_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    shared_eating_mode = Column(String(20), nullable=True)
    member_count = Column(SmallInteger, default=1, server_default="1")
    cuisine_prefs = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
