from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel


class SavedYouTubeChannelResponseDTO(BaseModel):
    id: int
    external_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    channel_url: Optional[str] = None
    thumbnails: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[datetime] = None
    video_count: int = 0

    class Config:
        from_attributes = True
