from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SpeakerProfileEntity(BaseModel):
    """Represents a known speaker profile with enrolled voice samples."""

    model_config = ConfigDict(from_attributes=True)

    id: str | None = None
    name: str
    description: str | None = None
    avatar_url: str | None = None
    samples_count: int = 0
    pending_count: int = 0
    centroid: list[float] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
