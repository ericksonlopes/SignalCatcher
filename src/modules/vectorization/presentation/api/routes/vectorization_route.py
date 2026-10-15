from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.core.logger.logger import logger
from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.diarization.presentation.api.dependencies import (
    get_diarization_repository,
)
from src.modules.vectorization.application.dtos.vectorization_status_dto import (
    VectorizationStatsDTO,
    VectorizationStatusDTO,
)
from src.modules.vectorization.application.use_cases.vectorize_diarization_use_case import (
    VectorizeDiarizationUseCase,
)
from src.modules.vectorization.domain.enums.source_type import SourceType
from src.modules.vectorization.domain.interfaces.repositories.chunk_repository_interface import (
    IChunkRepository,
)
from src.modules.vectorization.domain.interfaces.services.embedding_service_interface import (
    IEmbeddingService,
)
from src.modules.vectorization.presentation.api.dependencies import (
    get_chunk_repository,
    get_tei_embedding_service,
    get_vectorize_use_case,
)

router = APIRouter()


@router.post(
    "/diarization/{diarization_id}",
    summary="Vectorize a specific diarization task",
    responses={
        404: {"description": "Diarization task or audio not found"},
        500: {"description": "Vectorization failed"},
    },
)
def vectorize_diarization(
    diarization_id: str,
    use_case: Annotated[VectorizeDiarizationUseCase, Depends(get_vectorize_use_case)],
) -> VectorizationStatusDTO:
    """Chunks and embeds the transcript of a completed diarization task into pgvector."""
    try:
        return use_case.execute(diarization_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to vectorize diarization {diarization_id}: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Vectorization failed: {exc}"
        ) from exc


@router.get(
    "/status/{diarization_id}",
    summary="Check vectorization status for a diarization task",
    responses={
        404: {"description": "Diarization task not found"},
    },
)
def get_vectorization_status(
    diarization_id: str,
    chunk_repository: Annotated[IChunkRepository, Depends(get_chunk_repository)],
    diarization_repository: Annotated[
        IDiarizationRepository, Depends(get_diarization_repository)
    ],
) -> VectorizationStatusDTO:
    task = diarization_repository.get_task(diarization_id)
    if not task:
        raise HTTPException(status_code=404, detail="Diarization task not found")

    chunks = chunk_repository.get_chunks_by_source(
        SourceType.YOUTUBE_TRANSCRIPT.value, diarization_id
    )
    return VectorizationStatusDTO(
        diarization_id=diarization_id,
        content_id=task.entity_id,
        chunks_count=len(chunks),
        indexed=len(chunks) > 0,
    )


@router.get(
    "/stats",
    summary="Get vectorization and TEI cluster statistics",
)
def get_vectorization_stats(
    chunk_repository: Annotated[IChunkRepository, Depends(get_chunk_repository)],
    embedding_service: Annotated[IEmbeddingService, Depends(get_tei_embedding_service)],
) -> VectorizationStatsDTO:
    total_chunks = chunk_repository.count_total_chunks()
    total_indexed = chunk_repository.count_indexed_sources()
    tei_healthy = embedding_service.health_check()

    return VectorizationStatsDTO(
        total_chunks=total_chunks,
        total_indexed_diarizations=total_indexed,
        tei_healthy=tei_healthy,
    )


@router.post(
    "/batch",
    summary="Vectorize all un-indexed completed diarization tasks",
)
def batch_vectorize(
    use_case: Annotated[VectorizeDiarizationUseCase, Depends(get_vectorize_use_case)],
    chunk_repository: Annotated[IChunkRepository, Depends(get_chunk_repository)],
    diarization_repository: Annotated[
        IDiarizationRepository, Depends(get_diarization_repository)
    ],
) -> list[VectorizationStatusDTO]:
    """Finds COMPLETED tasks with result_json that don't have indexed chunks
    yet and vectorizes them.
    """
    tasks, _ = diarization_repository.get_paginated(page=1, limit=500, step="COMPLETED")
    results: list[VectorizationStatusDTO] = []

    for task in tasks:
        if not task.id or not task.result_json:
            continue
        existing_chunks = chunk_repository.get_chunks_by_source(
            SourceType.YOUTUBE_TRANSCRIPT.value, task.id
        )
        if not existing_chunks:
            try:
                status = use_case.execute(task.id)
                results.append(status)
            except Exception as exc:
                logger.error(f"Batch vectorization error on task {task.id}: {exc}")

    return results
