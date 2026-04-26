import uuid

from sqlalchemy import Boolean, Column, DateTime, SmallInteger, String, text, UUID

from app.database import Base


class OTPSession(Base):
    __tablename__ = "otp_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    phone = Column(String(15), nullable=False, index=True)
    otp_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(SmallInteger, default=0, server_default="0")
    is_used = Column(Boolean, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
