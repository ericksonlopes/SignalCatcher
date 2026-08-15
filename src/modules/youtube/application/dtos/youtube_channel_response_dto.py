from typing import Optional
from pydantic import BaseModel


class YouTubeChannelResponseDTO(BaseModel):
    id: int
    external_id: Optional[str] = None
    name: str
    url: str
    active: bool

    class Config:
        from_attributes = True

