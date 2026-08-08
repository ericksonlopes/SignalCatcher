from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from src.domain.models.enums.content_step import ContentStep

class ContentTrackingResponse(BaseModel):
    id: int
    previous_step: Optional[ContentStep]
    new_step: ContentStep
    changed_at: datetime
    details: Optional[str]
