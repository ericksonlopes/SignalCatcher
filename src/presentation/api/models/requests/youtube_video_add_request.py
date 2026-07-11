from pydantic import BaseModel

class YouTubeVideoAddRequest(BaseModel):
    url: str
