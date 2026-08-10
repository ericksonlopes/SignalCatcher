from datetime import datetime
from zoneinfo import ZoneInfo


def get_brazil_time():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)


from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from src.core.database.connector import Base


class YouTubeMonitoredChannelModel(Base):
    """YouTube channels that the scheduler should periodically monitor."""

    __tablename__ = "youtube_monitored_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(
        String, ForeignKey("youtube_channels.external_id"), nullable=False
    )
    url = Column(String, unique=True, nullable=False)  # Channel/profile URL
    active = Column(Boolean, nullable=False, default=True)  # Active/inactive
    created_at = Column(DateTime, default=get_brazil_time)
    last_checked_at = Column(DateTime, nullable=True)  # Last time it was checked

    # Relationship to the saved youtube_channels table
    channel_info = relationship("YouTubeChannelModel")

    def __repr__(self):
        return f"<YouTubeMonitoredChannelModel(external_id='{self.external_id}', active={self.active})>"
