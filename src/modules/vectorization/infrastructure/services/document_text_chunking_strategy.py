from typing import Any

from src.core.config.settings import settings
from src.modules.vectorization.domain.entities.vector_chunk_entity import (
    VectorChunkEntity,
)
from src.modules.vectorization.domain.enums.source_type import SourceType
from src.modules.vectorization.domain.interfaces.services.chunking_strategy_interface import (
    IChunkingStrategy,
)


class DocumentTextChunkingStrategy(IChunkingStrategy):
    """Generic text chunking strategy for documents (PDFs, Markdown, text files)."""

    def __init__(
        self,
        chunk_size_words: int | None = None,
        chunk_overlap_words: int = 50,
    ) -> None:
        self.chunk_size_words = chunk_size_words or settings.CHUNK_MAX_TOKENS_ESTIMATE
        self.chunk_overlap_words = chunk_overlap_words

    @property
    def supported_source_type(self) -> SourceType:
        return SourceType.DOCUMENT

    def create_chunks(
        self,
        source_id: str,
        content: Any,
        parent_id: str | None = None,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[VectorChunkEntity]:
        raw_text = content if isinstance(content, str) else str(content)
        words = raw_text.split()
        if not words:
            return []

        chunks: list[VectorChunkEntity] = []
        i = 0
        chunk_idx = 0
        step = max(1, self.chunk_size_words - self.chunk_overlap_words)

        while i < len(words):
            chunk_words = words[i : i + self.chunk_size_words]
            chunk_text = " ".join(chunk_words)

            chunks.append(
                VectorChunkEntity(
                    source_type=SourceType.DOCUMENT,
                    source_id=source_id,
                    parent_id=parent_id,
                    chunk_index=chunk_idx,
                    text=chunk_text,
                    metadata=base_metadata or {},
                )
            )
            chunk_idx += 1
            i += step

        return chunks
