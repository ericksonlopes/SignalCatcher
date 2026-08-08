from datetime import datetime
from zoneinfo import ZoneInfo

def get_brazil_time():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)

from sqlalchemy import Column, Integer, String, DateTime, Boolean

from src.infrastructure.repositories.connector import Base


class YouTubeMonitoredChannelModel(Base):
    """YouTube channels that the scheduler should periodically monitor."""
    __tablename__ = "youtube_monitored_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  # Friendly name (e.g., "Filipe Deschamps")
    url = Column(String, unique=True, nullable=False)  # Channel/profile URL
    active = Column(Boolean, nullable=False, default=True)  # Active/inactive
    created_at = Column(DateTime, default=get_brazil_time)
    last_checked_at = Column(DateTime, nullable=True)  # Last time it was checked

    def __repr__(self):
        return f"<YouTubeMonitoredChannelModel(name='{self.name}', active={self.active})>"
