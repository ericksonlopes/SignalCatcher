from typing import Optional

from pydantic import BaseModel


class YouTubeVideoDTO(BaseModel):
    id: str
    title: Optional[str] = None
    url: str
