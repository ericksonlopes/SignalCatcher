from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SavedYouTubeChannelResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    title: str | None = None
    description: str | None = None
    url: str | None = None
    channel_url: str | None = None
    thumbnails: list[dict[str, Any]] | None = None
    created_at: datetime | None = None
    video_count: int = 0
