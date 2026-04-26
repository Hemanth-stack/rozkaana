from sqlalchemy import Column, String, SmallInteger, DateTime, text, UUID, ARRAY, ForeignKey
from app.database import Base
import uuid

class Household(Base):
    __tablename__ = "households"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    name = Column(String(100))
    head_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    shared_eating_mode = Column(String(20))
    member_count = Column(SmallInteger)
    cuisine_prefs = Column(ARRAY(String))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))