from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from src.modules.youtube.domain.enums.content_step import ContentStep


class YoutubeVideoCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str  # Mapping external_id to id for the frontend
    title: str
    url: str
    channel_name: str  # Mapping origin
    step: ContentStep
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    file_path: Optional[str] = None
    language: Optional[str] = None
    is_diarized: bool = False
    diarization_status: Optional[str] = None
