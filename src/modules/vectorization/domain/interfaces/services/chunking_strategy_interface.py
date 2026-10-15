from abc import ABC, abstractmethod
from typing import Any

from src.modules.vectorization.domain.entities.vector_chunk_entity import (
    VectorChunkEntity,
)
from src.modules.vectorization.domain.enums.source_type import SourceType


class IChunkingStrategy(ABC):
    """Strategy interface for chunking various types of media (audio, text, web)."""

    @property
    @abstractmethod
    def supported_source_type(self) -> SourceType:
        pass

    @abstractmethod
    def create_chunks(
        self,
        source_id: str,
        content: Any,
        parent_id: str | None = None,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[VectorChunkEntity]:
        """Slices raw content into chunks with contextual metadata."""
        pass
