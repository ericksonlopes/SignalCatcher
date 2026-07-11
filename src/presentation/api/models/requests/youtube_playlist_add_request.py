from pydantic import BaseModel

class YouTubePlaylistAddRequest(BaseModel):
    url: str
