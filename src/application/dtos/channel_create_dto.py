from typing import Optional
from pydantic import BaseModel


class ChannelCreateDTO(BaseModel):
    external_id: Optional[str] = None
    name: Optional[str] = None
    url: str
