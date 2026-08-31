from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from src.modules.diarization.domain.enums.diarization_step import DiarizationStep


class DiarizationEntity(BaseModel):
    """A diarization task, independent of how it is stored."""

    id: Optional[str] = None
    file_path: str
    step: DiarizationStep = DiarizationStep.PENDING

    # Link back to whatever produced the audio (a YouTube content, for instance).
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None

    # Configuration handed to the diarization service.
    language: Optional[str] = None
    num_speakers: Optional[int] = None
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None
    model_size: str = "large-v2"

    # Results
    result_json: Optional[Any] = None
    error_message: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def is_cancellable(self) -> bool:
        return self.step in DiarizationStep.cancellable()
