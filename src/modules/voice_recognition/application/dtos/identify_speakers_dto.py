from pydantic import BaseModel, Field


class IdentifyDiarizationSpeakersRequestDTO(BaseModel):
    similarity_threshold: float = Field(default=0.65, ge=0.1, le=1.0)
    auto_apply: bool = Field(
        default=True,
        description=(
            "Automatically replace SPEAKER_XX labels with matched speaker profile names"
        ),
    )


class SpeakerMatchDTO(BaseModel):
    original_speaker_label: str
    current_speaker_label: str
    matched_speaker_id: str | None = None
    matched_speaker_name: str | None = None
    matched_sample_id: str | None = None
    similarity_score: float = 0.0
    segments_count: int = 0
    speech_duration_seconds: float = 0.0
    identified: bool = False
    applied: bool = False


class IdentifyDiarizationResponseDTO(BaseModel):
    diarization_id: str
    entity_id: str | None = None
    total_speakers: int
    identified_count: int
    auto_applied: bool
    matches: list[SpeakerMatchDTO]


class AssignSpeakerLabelDTO(BaseModel):
    speaker_label: str = Field(
        ...,
        min_length=1,
        description="Current or original speaker label in the diarization",
    )
    speaker_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="New speaker name to assign",
    )
    speaker_id: str | None = None
    enroll_voice: bool = Field(
        default=True,
        description="Whether to also extract and enroll the voiceprint into pgvector",
    )
