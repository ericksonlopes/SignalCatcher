from pydantic import BaseModel

from src.domain.models.youtube_video_dto import YouTubeVideoDTO


class YouTubeChannelResultDTO(BaseModel):
    channel_name: str
    videos: list[YouTubeVideoDTO]
