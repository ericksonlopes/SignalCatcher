from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ChannelEntity(BaseModel):
    id: Optional[int] = None
    name: str
    url: str
    active: bool = True
    created_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
