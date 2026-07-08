from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from src.domain.models.enums.source_platform import SourcePlatform


class SourceEntity(BaseModel):
    id: Optional[int] = None
    name: str
    url: str
    source_platform: SourcePlatform
    active: bool = True
    created_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
