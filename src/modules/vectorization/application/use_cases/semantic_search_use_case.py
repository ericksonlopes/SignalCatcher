import logging
from typing import Any

from src.modules.vectorization.application.dtos.search_query_dto import (
    SemanticSearchQueryDTO,
)
from src.modules.vectorization.application.dtos.search_result_dto import (
    SemanticSearchResultDTO,
)
from src.modules.vectorization.domain.entities.vector_chunk_entity import (
    VectorChunkEntity,
)
from src.modules.vectorization.domain.enums.source_type import SourceType
from src.modules.vectorization.domain.interfaces.repositories.chunk_repository_interface import (
    IChunkRepository,
)
from src.modules.vectorization.domain.interfaces.services.embedding_service_interface import (
    IEmbeddingService,
)
from src.modules.vectorization.infrastructure.services.audio_transcript_chunking_strategy import (
    format_timestamp,
)
from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)

logger = logging.getLogger(__name__)


class SemanticSearchUseCase:
    """Performs polymorphic semantic search over indexed chunks and enriches
    with source-specific metadata (YouTube videos, documents, websites).
    """

    def __init__(
        self,
        chunk_repository: IChunkRepository,
        embedding_service: IEmbeddingService,
        youtube_contents: IYoutubeContentService,
    ) -> None:
        self.chunk_repository = chunk_repository
        self.embedding_service = embedding_service
        self.youtube_contents = youtube_contents

    def execute(self, query: SemanticSearchQueryDTO) -> list[SemanticSearchResultDTO]:
        query_vector = self._get_query_vector(query.query)
        if not query_vector:
            return []

        matches = self.chunk_repository.similarity_search(
            query_vector=query_vector,
            top_k=query.limit,
            source_type=query.source_type,
            parent_id=query.parent_id,
            min_similarity=query.min_similarity,
        )
        if not matches:
            return []

        contents_map = self._fetch_youtube_contents(matches)
        return [
            self._to_search_result_dto(chunk, similarity, contents_map)
            for chunk, similarity in matches
        ]

    def _get_query_vector(self, query_text: str) -> list[float] | None:
        query_vectors = self.embedding_service.get_embeddings(
            [query_text], is_query=True
        )
        if not query_vectors:
            return None
        return query_vectors[0]

    def _fetch_youtube_contents(
        self, matches: list[tuple[VectorChunkEntity, float]]
    ) -> dict[str, Any]:
        yt_parent_ids = [
            chunk.parent_id
            for chunk, _ in matches
            if chunk.source_type == SourceType.YOUTUBE_TRANSCRIPT and chunk.parent_id
        ]
        if not yt_parent_ids:
            return {}
        return self.youtube_contents.get_many_by_external_ids(list(set(yt_parent_ids)))

    def _enrich_youtube(
        self, chunk: VectorChunkEntity, contents_map: dict[str, Any]
    ) -> tuple[str | None, str | None, str | None, str | None]:
        content = contents_map.get(chunk.parent_id or "")
        title = content.title if content else chunk.metadata.get("video_title")
        subtitle = content.origin if content else chunk.metadata.get("channel_name")
        thumbnail_url = (
            content.thumbnail if content else chunk.metadata.get("thumbnail")
        )

        deep_link = None
        if chunk.parent_id:
            start_sec = (
                int(round(chunk.start_time)) if chunk.start_time is not None else 0
            )
            deep_link = (
                f"https://www.youtube.com/watch?v={chunk.parent_id}&t={start_sec}s"
            )

        return title, subtitle, thumbnail_url, deep_link

    def _enrich_document(
        self, chunk: VectorChunkEntity
    ) -> tuple[str | None, str | None, str | None, str | None]:
        title = chunk.metadata.get("file_name", "Documento")
        subtitle = chunk.metadata.get("section") or chunk.metadata.get("author")
        deep_link = chunk.metadata.get("file_path")
        return title, subtitle, None, deep_link

    def _enrich_website(
        self, chunk: VectorChunkEntity
    ) -> tuple[str | None, str | None, str | None, str | None]:
        title = chunk.metadata.get("title") or chunk.metadata.get("h1", "Página Web")
        subtitle = chunk.metadata.get("domain") or chunk.metadata.get("url")
        deep_link = chunk.metadata.get("url")
        return title, subtitle, None, deep_link

    def _resolve_chunk_metadata(
        self, chunk: VectorChunkEntity, contents_map: dict[str, Any]
    ) -> tuple[str | None, str | None, str | None, str | None]:
        if chunk.source_type == SourceType.YOUTUBE_TRANSCRIPT:
            return self._enrich_youtube(chunk, contents_map)
        if chunk.source_type == SourceType.DOCUMENT:
            return self._enrich_document(chunk)
        if chunk.source_type == SourceType.WEBSITE:
            return self._enrich_website(chunk)
        return None, None, None, None

    def _to_search_result_dto(
        self,
        chunk: VectorChunkEntity,
        similarity: float,
        contents_map: dict[str, Any],
    ) -> SemanticSearchResultDTO:
        title, subtitle, thumbnail_url, deep_link = self._resolve_chunk_metadata(
            chunk, contents_map
        )
        is_youtube = chunk.source_type == SourceType.YOUTUBE_TRANSCRIPT

        return SemanticSearchResultDTO(
            chunk_id=chunk.id or "",
            source_type=chunk.source_type.value,
            source_id=chunk.source_id,
            parent_id=chunk.parent_id,
            title=title,
            subtitle=subtitle,
            thumbnail_url=thumbnail_url,
            text=chunk.text,
            similarity_score=round(similarity, 4),
            metadata=chunk.metadata,
            deep_link=deep_link,
            start_time=chunk.start_time,
            end_time=chunk.end_time,
            formatted_start_time=(
                format_timestamp(chunk.start_time)
                if chunk.start_time is not None
                else None
            ),
            formatted_end_time=(
                format_timestamp(chunk.end_time)
                if chunk.end_time is not None
                else None
            ),
            speaker=chunk.speaker,
            video_title=title,
            channel_title=subtitle,
            youtube_url_with_timestamp=deep_link if is_youtube else None,
        )
