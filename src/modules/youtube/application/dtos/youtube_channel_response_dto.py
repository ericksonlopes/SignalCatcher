from typing import Optional

from pydantic import BaseModel, ConfigDict


class YouTubeChannelResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: Optional[str] = None
    name: str
    url: str
    active: bool
