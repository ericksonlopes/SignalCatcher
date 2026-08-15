from typing import Optional, List

from pydantic import BaseModel

from src.modules.youtube.domain.enums.content_step import ContentStep


class YoutubeVideoCardResponse(BaseModel):
    id: str  # Mapping external_id to id for the frontend
    title: str
    url: str
    channel_name: str  # Mapping origin
    step: ContentStep
    thumbnail: Optional[str]
    duration: Optional[int]
    description: Optional[str] = None
    tags: Optional[List[str]]
    file_path: Optional[str] = None
    language: Optional[str] = None
    is_diarized: bool = False
    diarization_status: Optional[str] = None

    class Config:

        from_attributes = True
