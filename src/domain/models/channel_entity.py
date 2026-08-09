from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ChannelEntity(BaseModel):
    id: Optional[int] = None
    external_id: str
    name: Optional[str] = None
    url: str
    active: bool = True
    created_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
