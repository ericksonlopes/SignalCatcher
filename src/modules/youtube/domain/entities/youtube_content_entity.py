from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.modules.youtube.domain.enums.content_step import ContentStep


class YoutubeContentEntity(BaseModel):
    id: Optional[int] = None
    external_id: str
    title: str
    url: str
    origin: str
    step: ContentStep
    raw_metadata: Optional[dict] = None
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    categories: Optional[list] = None
    tags: Optional[list[str]] = None
    file_path: Optional[str] = None
    language: Optional[str] = None
    error_info: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
