from sqlalchemy import Column, String, SmallInteger, Boolean, DateTime, text, UUID
from app.database import Base
import uuid

class OTPSession(Base):
    __tablename__ = "otp_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    phone = Column(String(15), index=True)
    otp_hash = Column(String(64))
    expires_at = Column(DateTime(timezone=True))
    attempts = Column(SmallInteger)
    is_used = Column(Boolean)