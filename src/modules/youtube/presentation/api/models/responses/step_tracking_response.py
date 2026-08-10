from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.modules.youtube.domain.enums.content_step import ContentStep


class StepTrackingResponse(BaseModel):
    id: int
    previous_step: Optional[ContentStep]
    new_step: ContentStep
    changed_at: datetime
    details: Optional[str]
