from datetime import datetime
from zoneinfo import ZoneInfo

def get_brazil_time():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)

from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean

from src.infrastructure.repositories.connector import Base
from src.domain.models.enums.source_platform import SourcePlatform


class MonitoredSourceModel(Base):
    """Sources that the scheduler should periodically monitor."""
    __tablename__ = "monitored_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  # Friendly name (e.g., "Filipe Deschamps")
    url = Column(String, unique=True, nullable=False)  # Channel/profile URL
    source_platform = Column(Enum(SourcePlatform), nullable=False, default=SourcePlatform.YOUTUBE)  # Source platform
    active = Column(Boolean, nullable=False, default=True)  # Active/inactive
    created_at = Column(DateTime, default=get_brazil_time)
    last_checked_at = Column(DateTime, nullable=True)  # Last time it was checked

    def __repr__(self):
        return f"<MonitoredSourceModel(name='{self.name}', source_platform='{self.source_platform}', active={self.active})>"
