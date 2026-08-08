from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, String, DateTime, JSON, Integer

from src.infrastructure.repositories.connector import Base


def get_brazil_time():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)


class YouTubeChannelModel(Base):
    """YouTube channels metadata extracted from the scraper."""

    __tablename__ = "youtube_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(
        String, unique=True, nullable=False
    )  # Using external ID (e.g. "@IShowSpeed")
    title = Column(String, nullable=True)
    description = Column(String, nullable=True)
    url = Column(String, nullable=True)
    channel_url = Column(String, nullable=True)
    thumbnails = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=get_brazil_time)
    updated_at = Column(DateTime, default=get_brazil_time, onupdate=get_brazil_time)

    def __repr__(self):
        return f"<YouTubeChannelModel(id='{self.id}', title='{self.title}')>"
