import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)

from src.core.config.settings import settings
from src.core.database.connector import Base


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SpeakerProfileModel(Base):
    __tablename__ = "speaker_profiles"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    avatar_url = Column(String(512), nullable=True)
    samples_count = Column(Integer, nullable=False, default=0, server_default="0")
    pending_count = Column(Integer, nullable=False, default=0, server_default="0")
    centroid = Column(Vector(settings.VOICE_EMBEDDING_DIMENSION), nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)


class VoiceSampleModel(Base):
    __tablename__ = "voice_samples"
    __table_args__ = (
        Index(
            "ix_voice_samples_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_voice_samples_speaker_id", "speaker_id"),
        Index("ix_voice_samples_source", "source_type", "source_id"),
        Index("ix_voice_samples_status", "status"),
        Index("ix_voice_samples_speaker_status", "speaker_id", "status"),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    speaker_id = Column(
        String,
        ForeignKey("speaker_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type = Column(String(50), nullable=False, default="DIARIZATION_SEGMENT")
    source_id = Column(String(255), nullable=True)
    speaker_label = Column(String(100), nullable=True)
    start_time = Column(Float, nullable=True)
    end_time = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    status = Column(
        String(30), nullable=False, default="PENDING_REVIEW", server_default="PENDING_REVIEW"
    )
    clip_path = Column(String(1024), nullable=True)
    quality = Column(JSON, nullable=False, default=dict)
    reviewed_at = Column(DateTime, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    embedding = Column(Vector(settings.VOICE_EMBEDDING_DIMENSION), nullable=False)
    created_at = Column(DateTime, default=get_utc_now)
