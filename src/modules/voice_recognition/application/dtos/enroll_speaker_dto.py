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
    selected_segment_indices: list[int] | None = Field(
        default=None,
        description="Optional list of specific segment indices to train from",
    )
    start_time: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional custom start time of clip in seconds",
    )
    end_time: float | None = Field(
        default=None,
        gt=0.0,
        description="Optional custom end time of clip in seconds",
    )


class EnrollFromVideoClipDTO(BaseModel):
    video_id: str = Field(
        ...,
        min_length=1,
        description="Diarization ID, YouTube external ID, or local media path",
    )
    speaker_name: str | None = Field(
        default=None,
        description="Speaker name (creates or reuses profile if speaker_id is omitted)",
    )
    speaker_id: str | None = Field(
        default=None,
        description="Existing speaker profile ID to append this sample to",
    )
    start_time: float = Field(
        ...,
        ge=0.0,
        description="Start time of the speech clip in seconds",
    )
    end_time: float = Field(
        ...,
        gt=0.0,
        description="End time of the speech clip in seconds",
    )
    description: str | None = None
    label: str | None = Field(
        default=None,
        description="Optional descriptive label for this sample clip",
    )


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
