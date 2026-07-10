from datetime import datetime
from zoneinfo import ZoneInfo

def get_brazil_time():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)

from sqlalchemy import Column, Integer, String, DateTime, Enum

from src.infrastructure.repositories.connector import Base
from src.domain.models.enums.content_status import ContentStatus
from src.domain.models.enums.source_platform import SourcePlatform


class ContentModel(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String, unique=True, nullable=False, index=True)  # ID on the source platform
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    source_platform = Column(Enum(SourcePlatform), nullable=False, default=SourcePlatform.YOUTUBE)  # Source platform
    origin = Column(String, nullable=False)  # Where the content came from (e.g., channel/profile name)
    status = Column(Enum(ContentStatus), nullable=False, default=ContentStatus.PENDING_DOWNLOAD)
    created_at = Column(DateTime, default=get_brazil_time)
    updated_at = Column(DateTime, default=get_brazil_time,
                        onupdate=get_brazil_time)

    def __repr__(self):
        return f"<ContentModel(external_id='{self.external_id}', source_platform='{self.source_platform}', status='{self.status}')>"
