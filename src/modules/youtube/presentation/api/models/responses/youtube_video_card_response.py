from typing import Optional, List
from pydantic import BaseModel
from src.modules.youtube.domain.enums.content_step import ContentStep

class YoutubeVideoCardResponse(BaseModel):
    id: str # Mapping external_id to id for the frontend
    title: str
    url: str
    channel_name: str # Mapping origin
    step: ContentStep
    thumbnail: Optional[str]
    duration: Optional[str]
    description: Optional[str] = None
    tags: Optional[List[str]]
    
    class Config:
        from_attributes = True
