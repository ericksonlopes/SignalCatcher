from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateSpeakerProfileDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    avatar_url: str | None = None


class UpdateSpeakerProfileDTO(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    avatar_url: str | None = None


class VoiceSampleResponseDTO(BaseModel):
    id: str
    speaker_id: str
    source_type: str
    source_id: str | None = None
    speaker_label: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    duration_seconds: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class SpeakerProfileResponseDTO(BaseModel):
    id: str
    name: str
    description: str | None = None
    avatar_url: str | None = None
    samples_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    samples: list[VoiceSampleResponseDTO] | None = None


class VoiceRecognitionStatsDTO(BaseModel):
    total_profiles: int
    total_samples: int
    embedding_dimension: int
    default_similarity_threshold: float
    worker_healthy: bool
