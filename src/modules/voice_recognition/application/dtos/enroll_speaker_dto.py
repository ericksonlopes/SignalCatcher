from pydantic import BaseModel, Field


class EnrollFromDiarizationDTO(BaseModel):
    diarization_id: str = Field(..., min_length=1)
    speaker_label: str = Field(
        ...,
        min_length=1,
        description="Original or current speaker label in the diarization (e.g. SPEAKER_00)",
    )
    speaker_id: str | None = Field(default=None, description="Existing speaker profile ID")
    speaker_name: str | None = Field(
        default=None,
        description="Speaker name (creates or reuses profile if speaker_id is omitted)",
    )
    description: str | None = None
    apply_to_diarization: bool = True


class EnrollResponseDTO(BaseModel):
    speaker_id: str
    speaker_name: str
    sample_id: str
    source_type: str
    source_id: str | None = None
    speaker_label: str | None = None
    segments_used: int = 0
    speech_duration_seconds: float = 0.0
    applied_to_diarization: bool = False
    samples_count: int = 1
