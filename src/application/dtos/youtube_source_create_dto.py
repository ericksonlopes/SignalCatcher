from pydantic import BaseModel


class YouTubeSourceCreateDTO(BaseModel):
    name: str
    url: str
