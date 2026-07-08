from pydantic import BaseModel

from src.domain.models.enums.source_platform import SourcePlatform


class SourceResponseDTO(BaseModel):
    id: int
    name: str
    url: str
    source_platform: SourcePlatform
    active: bool

    class Config:
        from_attributes = True
