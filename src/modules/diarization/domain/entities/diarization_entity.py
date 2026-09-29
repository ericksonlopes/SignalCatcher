from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.modules.diarization.domain.enums.diarization_step import DiarizationStep


class DiarizationEntity(BaseModel):
    """A diarization task, independent of how it is stored."""

    id: str | None = None
    file_path: str
    step: DiarizationStep = DiarizationStep.PENDING

    # Link back to whatever produced the audio (a YouTube content, for instance).
    entity_id: str | None = None
    entity_type: str | None = None

    # Configuration handed to the diarization service.
    language: str | None = None
    num_speakers: int | None = None
    min_speakers: int | None = None
    max_speakers: int | None = None
    model_size: str = "large-v2"

    # Results
    result_json: Any | None = None
    error_message: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_cancellable(self) -> bool:
        return self.step in DiarizationStep.cancellable()
