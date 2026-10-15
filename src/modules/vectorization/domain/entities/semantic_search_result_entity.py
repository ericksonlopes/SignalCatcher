from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.modules.vectorization.domain.enums.source_type import SourceType


class SemanticSearchResultEntity(BaseModel):
    """Polymorphic semantic search result representing any indexed media source."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    source_type: SourceType
    source_id: str
    parent_id: str | None = None
    title: str | None = None
    subtitle: str | None = None
    thumbnail_url: str | None = None
    text: str
    similarity_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    deep_link: str | None = None
