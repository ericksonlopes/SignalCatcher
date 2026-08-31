from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class SavedYouTubeChannelResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    channel_url: Optional[str] = None
    thumbnails: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[datetime] = None
    video_count: int = 0
