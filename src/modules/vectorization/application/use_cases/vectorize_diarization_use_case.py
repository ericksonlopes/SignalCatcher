import logging

from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.vectorization.application.dtos.vectorization_status_dto import (
    VectorizationStatusDTO,
)
from src.modules.vectorization.domain.enums.source_type import SourceType
from src.modules.vectorization.domain.interfaces.repositories.chunk_repository_interface import (
    IChunkRepository,
)
from src.modules.vectorization.domain.interfaces.services.chunking_strategy_interface import (
    IChunkingStrategy,
)
from src.modules.vectorization.domain.interfaces.services.embedding_service_interface import (
    IEmbeddingService,
)

logger = logging.getLogger(__name__)


class VectorizeDiarizationUseCase:
    """Orchestrates chunking, embedding generation via TEI, and persistence for a diarization."""

    def __init__(
        self,
        chunk_repository: IChunkRepository,
        embedding_service: IEmbeddingService,
        chunking_strategy: IChunkingStrategy,
        diarization_repository: IDiarizationRepository,
    ) -> None:
        self.chunk_repository = chunk_repository
        self.embedding_service = embedding_service
        self.chunking_strategy = chunking_strategy
        self.diarization_repository = diarization_repository

    def execute(self, diarization_id: str) -> VectorizationStatusDTO:
        # 1. Fetch the diarization task
        task = self.diarization_repository.get_task(diarization_id)
        if not task:
            raise ValueError(f"Diarization task '{diarization_id}' not found")

        if not task.result_json:
            raise ValueError(
                f"Diarization task '{diarization_id}' does not have result_json yet "
                f"(step: {task.step})"
            )

        content_id = task.entity_id or diarization_id

        # 2. Slice result_json into time-aware chunks using polymorphic chunking strategy
        chunks = self.chunking_strategy.create_chunks(
            source_id=diarization_id,
            content=task.result_json,
            parent_id=content_id,
        )

        if not chunks:
            logger.warning("No chunks generated for diarization %s", diarization_id)
            return VectorizationStatusDTO(
                diarization_id=diarization_id,
                content_id=content_id,
                chunks_count=0,
                indexed=False,
            )

        # 3. Generate embeddings via TEI
        texts_to_embed = [chunk.text for chunk in chunks]
        embeddings = self.embedding_service.get_embeddings(
            texts_to_embed, is_query=False
        )

        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Mismatch between chunks ({len(chunks)}) and embeddings "
                f"returned ({len(embeddings)})"
            )

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            chunk.embedding = embedding

        # 4. Atomic replace: remove existing chunks for this task and persist new ones
        self.chunk_repository.delete_by_source(
            SourceType.YOUTUBE_TRANSCRIPT.value, diarization_id
        )
        self.chunk_repository.save_chunks(chunks)

        logger.info(
            "Successfully vectorized diarization %s (%d chunks created)",
            diarization_id,
            len(chunks),
        )

        return VectorizationStatusDTO(
            diarization_id=diarization_id,
            content_id=content_id,
            chunks_count=len(chunks),
            indexed=True,
        )
