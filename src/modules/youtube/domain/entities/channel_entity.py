from datetime import datetime

from pydantic import BaseModel


class ChannelEntity(BaseModel):
    id: int | None = None
    external_id: str
    name: str | None = None
    url: str
    active: bool = True
    created_at: datetime | None = None
    last_checked_at: datetime | None = None
