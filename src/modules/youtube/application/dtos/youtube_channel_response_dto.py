from pydantic import BaseModel


class YouTubeChannelResponseDTO(BaseModel):
    id: int
    name: str
    url: str
    active: bool

    class Config:
        from_attributes = True
