import uuid

from sqlalchemy import Column, Date, ForeignKey, String, UUID, text

from app.database import Base

class MenuHistory(Base):
    __tablename__ = "menu_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    date = Column(Date)
    pdf_url = Column(String)