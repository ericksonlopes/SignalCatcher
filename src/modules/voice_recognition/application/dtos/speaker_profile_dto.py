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
    status: str = "PENDING_REVIEW"
    clip_path: str | None = None
    has_audio: bool = False
    quality: dict[str, Any] = Field(default_factory=dict)
    reviewed_at: datetime | None = None
    embedding_model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class SpeakerProfileResponseDTO(BaseModel):
    id: str
    name: str
    description: str | None = None
    avatar_url: str | None = None
    samples_count: int = 0
    pending_count: int = 0
    profile_strength: str = "weak"  # "weak" | "moderate" | "strong"
    has_centroid: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    samples: list[VoiceSampleResponseDTO] | None = None


class VoiceRecognitionStatsDTO(BaseModel):
    total_profiles: int
    total_samples: int
    pending_samples: int = 0
    approved_samples: int = 0
    embedding_dimension: int
    default_similarity_threshold: float
    worker_healthy: bool


class ReviewSampleRequestDTO(BaseModel):
    status: str = Field(..., description="'APPROVED' or 'REJECTED'")
    start_time: float | None = None
    end_time: float | None = None


class BulkReviewSamplesRequestDTO(BaseModel):
    sample_ids: list[str] = Field(..., min_length=1)
    status: str = Field(..., description="'APPROVED' or 'REJECTED'")


class SuggestedClipDTO(BaseModel):
    start: float
    end: float
    duration: float
    text: str
    energy_score: float = 1.0
    has_overlap: bool = False
    quality_hint: str = "good"  # "good" | "short" | "overlap"
