"""SQLAlchemy mapping for VoiceSample."""

from sqlalchemy import JSON, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.connector import Base


class VoiceSample(Base):
    __tablename__ = "voice_samples"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    person_id: Mapped[str] = mapped_column(String, index=True)
    task_id: Mapped[str] = mapped_column(String)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String)
    embedding: Mapped[list] = mapped_column(JSON)
    video_path: Mapped[str] = mapped_column(String)
    audio_path: Mapped[str] = mapped_column(String)
