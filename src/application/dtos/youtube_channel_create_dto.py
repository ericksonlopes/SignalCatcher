from pydantic import BaseModel


class YouTubeChannelCreateDTO(BaseModel):
    name: str
    url: str
