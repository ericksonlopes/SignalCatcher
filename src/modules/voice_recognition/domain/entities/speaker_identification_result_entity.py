from pydantic import BaseModel


class SpeakerIdentificationMatchEntity(BaseModel):
    """Represents the voice recognition result for a single anonymous speaker cluster."""

    original_speaker_label: str
    matched_speaker_id: str | None = None
    matched_speaker_name: str | None = None
    matched_sample_id: str | None = None
    similarity_score: float = 0.0
    segments_count: int = 0
    speech_duration_seconds: float = 0.0
    identified: bool = False
    applied: bool = False
