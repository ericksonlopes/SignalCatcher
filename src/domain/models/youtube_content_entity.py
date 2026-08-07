from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.domain.models.enums.content_step import ContentStep
from src.domain.models.enums.source_platform import SourcePlatform


class YoutubeContentEntity(BaseModel):
    id: Optional[int] = None
    external_id: str
    title: str
    url: str
    source_platform: SourcePlatform
    origin: str
    step: ContentStep
    raw_metadata: Optional[dict] = None
    thumbnail: Optional[str] = None
    duration: Optional[str] = None
    categories: Optional[list] = None
    tags: Optional[list] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
