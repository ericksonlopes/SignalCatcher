from typing import Optional

from pydantic import BaseModel


class YouTubeVideo(BaseModel):
    id: str
    title: Optional[str] = None
    url: str
