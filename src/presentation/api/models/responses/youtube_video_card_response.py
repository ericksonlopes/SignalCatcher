from typing import Optional, List
from pydantic import BaseModel

class YoutubeVideoCardResponse(BaseModel):
    id: str # Mapping external_id to id for the frontend
    title: str
    url: str
    channel_name: str # Mapping origin
    thumbnail: Optional[str]
    duration: Optional[str]
    tags: Optional[List[str]]
    
    class Config:
        from_attributes = True
