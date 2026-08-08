from pydantic import BaseModel


class ChannelResponseDTO(BaseModel):
    id: int
    name: str
    url: str
    active: bool

    class Config:
        from_attributes = True
