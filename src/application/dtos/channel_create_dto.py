from pydantic import BaseModel


class ChannelCreateDTO(BaseModel):
    name: str
    url: str
