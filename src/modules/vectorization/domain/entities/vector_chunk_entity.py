from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.modules.vectorization.domain.enums.source_type import SourceType


class VectorChunkEntity(BaseModel):
    """Polymorphic vector chunk capable of holding transcripts, documents, websites, etc."""

    model_config = ConfigDict(from_attributes=True)

    id: str | None = None
    source_type: SourceType = SourceType.YOUTUBE_TRANSCRIPT
    source_id: str
    parent_id: str | None = None
    chunk_index: int
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: datetime | None = None

    @property
    def start_time(self) -> float | None:
        val = self.metadata.get("start_time")
        return float(val) if val is not None else None

    @property
    def end_time(self) -> float | None:
        val = self.metadata.get("end_time")
        return float(val) if val is not None else None

    @property
    def speaker(self) -> str | None:
        return self.metadata.get("speaker")
