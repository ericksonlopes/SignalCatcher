from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, Index, Integer, String

from src.core.database.connector import Base
from src.modules.youtube.domain.enums.content_step import ContentStep


def get_brazil_time():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)


class YoutubeContentModel(Base):
    __tablename__ = "youtube_contents"
    __table_args__ = (
        Index("ix_youtube_processing_queue", "step", "next_retry_at", "id"),
        Index("ix_youtube_deletion_queue", "deletion_requested", "next_retry_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(
        String, unique=True, nullable=False, index=True
    )  # ID on the external platform
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    origin = Column(
        String, nullable=False
    )  # Where the content came from (e.g., channel/profile name)
    step = Column(Enum(ContentStep), nullable=False, default=ContentStep.STARTED)
    error_info = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)  # Store specific error details
    raw_metadata = Column(JSON, nullable=True)  # Store extracted metadata JSON
    thumbnail = Column(String, nullable=True)
    duration = Column(Integer, nullable=True)  # Format: Seconds
    language = Column(String, nullable=True)  # Extracted language from raw_metadata
    lease_token = Column(String, nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    deletion_requested = Column(Boolean, nullable=False, default=False, server_default="false")
    deletion_attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    categories = Column(JSON, nullable=True)  # List of categories
    tags = Column(JSON, nullable=True)  # List of tags
    file_path = Column(String, nullable=True)  # Absolute path to the downloaded audio/video file
    created_at = Column(DateTime, default=get_brazil_time)
    updated_at = Column(DateTime, default=get_brazil_time, onupdate=get_brazil_time)

    def __repr__(self):
        return f"<YoutubeContentModel(external_id='{self.external_id}', step='{self.step}')>"
