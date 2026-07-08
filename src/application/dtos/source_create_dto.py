from pydantic import BaseModel

from src.domain.models.enums.source_platform import SourcePlatform


class SourceCreateDTO(BaseModel):
    name: str
    url: str
    source_platform: SourcePlatform
