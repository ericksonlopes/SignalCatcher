from abc import ABC, abstractmethod

from src.modules.vectorization.domain.entities.vector_chunk_entity import (
    VectorChunkEntity,
)


class IChunkRepository(ABC):
    @abstractmethod
    def save_chunks(self, chunks: list[VectorChunkEntity]) -> None:
        """Saves a batch of vector chunks."""
        pass

    @abstractmethod
    def delete_by_source(self, source_type: str, source_id: str) -> int:
        """Deletes all chunks for a specific source_type and source_id."""
        pass

    @abstractmethod
    def get_chunks_by_source(self, source_type: str, source_id: str) -> list[VectorChunkEntity]:
        """Returns all chunks for a source ordered by chunk_index."""
        pass

    @abstractmethod
    def count_indexed_sources(self, source_type: str | None = None) -> int:
        """Counts how many distinct sources have indexed chunks."""
        pass

    @abstractmethod
    def count_total_chunks(self, source_type: str | None = None) -> int:
        """Counts total chunks, optionally filtered by source_type."""
        pass

    @abstractmethod
    def similarity_search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        source_type: str | None = None,
        parent_id: str | None = None,
        min_similarity: float = 0.3,
    ) -> list[tuple[VectorChunkEntity, float]]:
        """Searches chunks nearest to query_vector using cosine similarity."""
        pass
