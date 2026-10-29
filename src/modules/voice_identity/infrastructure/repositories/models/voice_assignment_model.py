"""SQLAlchemy mapping for VoiceAssignment."""

from uuid import uuid4

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.connector import Base


class VoiceAssignment(Base):
    __tablename__ = "voice_assignments"
    __table_args__ = (UniqueConstraint("task_id", "version", "speaker"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[str] = mapped_column(String)
    speaker: Mapped[str] = mapped_column(String)
    person_id: Mapped[str | None] = mapped_column(String, nullable=True)
