from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.modules.youtube.domain.enums.content_step import ContentStep


class YoutubeVideoCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str  # Mapping external_id to id for the frontend
    title: str
    url: str
    channel_name: str  # Mapping origin
    step: ContentStep
    thumbnail: str | None = None
    duration: int | None = None
    description: str | None = None
    tags: list[str] | None = None
    file_path: str | None = None
    language: str | None = None
    is_diarized: bool = False
    diarization_status: str | None = None
    deletion_requested: bool = False
    attempt_count: int = 0
    next_retry_at: datetime | None = None
    error_info: str | None = None
    created_at: datetime | None = None
    published_at: datetime | None = None
