from typing import Any

from pydantic import BaseModel, Field


class SemanticSearchResultDTO(BaseModel):
    chunk_id: str
    source_type: str
    source_id: str
    parent_id: str | None = None
    title: str | None = None
    subtitle: str | None = None
    thumbnail_url: str | None = None
    text: str
    similarity_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    deep_link: str | None = None

    # Audio/Video convenience fields
    start_time: float | None = None
    end_time: float | None = None
    formatted_start_time: str | None = None
    formatted_end_time: str | None = None
    speaker: str | None = None
    video_title: str | None = None
    channel_title: str | None = None
    youtube_url_with_timestamp: str | None = None
