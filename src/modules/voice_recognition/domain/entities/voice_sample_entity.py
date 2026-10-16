from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.modules.voice_recognition.domain.enums.voice_source_type import VoiceSourceType


class VoiceSampleEntity(BaseModel):
    """Represents a single voiceprint embedding vector enrolled for a speaker profile."""

    model_config = ConfigDict(from_attributes=True)

    id: str | None = None
    speaker_id: str
    source_type: VoiceSourceType = VoiceSourceType.DIARIZATION_SEGMENT
    source_id: str | None = None
    speaker_label: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    duration_seconds: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: datetime | None = None
