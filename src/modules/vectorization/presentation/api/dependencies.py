from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends

from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.diarization.presentation.api.dependencies import (
    get_diarization_repository,
)
from src.modules.vectorization.application.use_cases.semantic_search_use_case import (
    SemanticSearchUseCase,
)
from src.modules.vectorization.application.use_cases.vectorize_diarization_use_case import (
    VectorizeDiarizationUseCase,
)
from src.modules.vectorization.domain.interfaces.repositories.chunk_repository_interface import (
    IChunkRepository,
)
from src.modules.vectorization.domain.interfaces.services.chunking_strategy_interface import (
    IChunkingStrategy,
)
from src.modules.vectorization.domain.interfaces.services.embedding_service_interface import (
    IEmbeddingService,
)
from src.modules.vectorization.infrastructure.services.audio_transcript_chunking_strategy import (
    AudioTranscriptChunkingStrategy,
)
from src.modules.vectorization.infrastructure.services.document_text_chunking_strategy import (
    DocumentTextChunkingStrategy,
)
from src.modules.vectorization.infrastructure.services.tei_embedding_service import (
    TeiEmbeddingService,
)
from src.modules.vectorization.infrastructure.unit_of_work import (
    VectorizationUnitOfWork,
)
from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)
from src.modules.youtube.presentation.api.dependencies import (
    get_youtube_content_service,
)


def get_vectorization_unit_of_work() -> Iterator[VectorizationUnitOfWork]:
    """Provides one database transaction per vectorization request."""
    with VectorizationUnitOfWork() as uow:
        yield uow
        uow.commit()


def get_chunk_repository(
    uow: VectorizationUnitOfWork = Depends(get_vectorization_unit_of_work),
) -> IChunkRepository:
    return uow.chunks


@lru_cache(maxsize=1)
def get_tei_embedding_service() -> IEmbeddingService:
    return TeiEmbeddingService()


@lru_cache(maxsize=1)
def get_audio_chunking_strategy() -> IChunkingStrategy:
    return AudioTranscriptChunkingStrategy()


@lru_cache(maxsize=1)
def get_document_chunking_strategy() -> IChunkingStrategy:
    return DocumentTextChunkingStrategy()


def get_vectorize_use_case(
    chunk_repository: IChunkRepository = Depends(get_chunk_repository),
    embedding_service: IEmbeddingService = Depends(get_tei_embedding_service),
    chunking_strategy: IChunkingStrategy = Depends(get_audio_chunking_strategy),
    diarization_repository: IDiarizationRepository = Depends(get_diarization_repository),
) -> VectorizeDiarizationUseCase:
    return VectorizeDiarizationUseCase(
        chunk_repository=chunk_repository,
        embedding_service=embedding_service,
        chunking_strategy=chunking_strategy,
        diarization_repository=diarization_repository,
    )


def get_semantic_search_use_case(
    chunk_repository: IChunkRepository = Depends(get_chunk_repository),
    embedding_service: IEmbeddingService = Depends(get_tei_embedding_service),
    youtube_contents: IYoutubeContentService = Depends(get_youtube_content_service),
) -> SemanticSearchUseCase:
    return SemanticSearchUseCase(
        chunk_repository=chunk_repository,
        embedding_service=embedding_service,
        youtube_contents=youtube_contents,
    )
