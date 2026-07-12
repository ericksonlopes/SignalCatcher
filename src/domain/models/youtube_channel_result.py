from typing import List

from pydantic import BaseModel

from src.domain.models.youtube_video import YouTubeVideo


class YouTubeChannelResult(BaseModel):
    channel_name: str
    videos: List[YouTubeVideo]
