from pydantic import BaseModel


class ChannelCreateDTO(BaseModel):
    external_id: str | None = None
    name: str | None = None
    url: str
