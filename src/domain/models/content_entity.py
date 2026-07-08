from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.domain.models.enums.content_status import ContentStatus
from src.domain.models.enums.source_platform import SourcePlatform


class ContentEntity(BaseModel):
    id: Optional[int] = None
    external_id: str
    title: str
    url: str
    source_platform: SourcePlatform
    origin: str
    status: ContentStatus
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
