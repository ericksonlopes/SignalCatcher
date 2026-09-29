from datetime import datetime

from pydantic import BaseModel

from src.modules.youtube.domain.enums.content_step import ContentStep


class StepTrackingResponse(BaseModel):
    id: int
    previous_step: ContentStep | None = None
    new_step: ContentStep
    changed_at: datetime
    details: str | None = None
