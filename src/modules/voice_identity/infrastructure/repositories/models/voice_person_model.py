"""SQLAlchemy mapping for VoicePerson."""

from uuid import uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.connector import Base


class VoicePerson(Base):
    __tablename__ = "voice_people"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
