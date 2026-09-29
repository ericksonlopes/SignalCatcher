from datetime import datetime

from pydantic import BaseModel, Field

from src.modules.youtube.domain.enums.content_step import ContentStep


class YoutubeContentEntity(BaseModel):
    id: int | None = None
    external_id: str
    title: str
    url: str
    origin: str
    step: ContentStep
    raw_metadata: dict | None = None
    thumbnail: str | None = None
    duration: int | None = None
    categories: list | None = None
    tags: list[str] | None = None
    file_path: str | None = None
    language: str | None = None
    error_info: str | None = None
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    lease_token: str | None = Field(default=None, exclude=True)
    lease_expires_at: datetime | None = None
    attempt_count: int = 0
    next_retry_at: datetime | None = None
    deletion_requested: bool = False
    deletion_attempt_count: int = 0
