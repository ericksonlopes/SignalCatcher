import math
from typing import Annotated, Optional, List, Any

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from src.core.logger.logger import logger
from src.modules.diarization.infrastructure.services.diarization_service import (
    DiarizationService,
)

router = APIRouter()


def get_diarization_service():
    return DiarizationService()


class DiarizationRequest(BaseModel):
    language: Optional[str] = "en"


class DiarizationCardResponse(BaseModel):
    id: str
    step: str
    created_at: Optional[str] = None
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    title: str
    channelName: str
    thumbnail: str
    duration: str
    result_json: Optional[Any] = None


class PaginatedDiarizationResponse(BaseModel):
    items: List[DiarizationCardResponse]
    diarizations: List[DiarizationCardResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    status_counts: Optional[dict[str, int]] = None
    total_status_count: Optional[int] = None


@router.post(
    "/youtube/{external_id}",
    responses={404: {"description": "Content not found"}},
)
def trigger_youtube_diarization(
    external_id: str,
    request: DiarizationRequest,
    service: Annotated[DiarizationService, Depends(get_diarization_service)],
):
    """
    Creates a diarization task for a completed YouTube content.
    """
    from src.modules.youtube.application.use_cases.content.content_queries import (
        ContentQueries,
    )
    from src.modules.youtube.infrastructure.services.youtube_content_service import (
        YoutubeContentService,
    )
    from src.modules.youtube.infrastructure.repositories.youtube_content_repository import (
        YoutubeContentRepository,
    )
    from src.modules.youtube.domain.enums.content_step import ContentStep

    try:
        # Resolve dependencies to get content - tight coupling, but necessary without a global DI container
        from src.core.logger.logger import logger as yt_logger
        youtube_repo = YoutubeContentRepository(logger=yt_logger)
        youtube_service = YoutubeContentService(repository=youtube_repo, logger=yt_logger)
        queries = ContentQueries(youtube_service)

        content = queries.get_content_by_external_id(external_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        if (
            content.step != ContentStep.COMPLETED.name
            and content.step != ContentStep.COMPLETED
        ):
            raise HTTPException(
                status_code=400, detail="Content must be completed to diarize"
            )

        if not content.file_path:
            raise HTTPException(status_code=400, detail="Content file path is missing")

        task = service.create_task(
            file_path=content.file_path,
            entity_id=content.external_id,
            entity_type="YOUTUBE",
            language=request.language or "en",
        )

        return {
            "message": f"Diarization task created for content {external_id}",
            "task_id": task.id,
        }
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create diarization task for {external_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/list",
    response_model=PaginatedDiarizationResponse,
    responses={500: {"description": "Internal server error"}},
)
@router.get(
    "/",
    response_model=PaginatedDiarizationResponse,
    responses={500: {"description": "Internal server error"}},
)
def get_diarizations(
    service: Annotated[DiarizationService, Depends(get_diarization_service)],
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    step: Optional[str] = Query(None, description="Filter by step status"),
    search: Optional[str] = Query(None, description="Search by title or channel"),
):
    """
    Returns a paginated list of diarizations enriched with YouTube content details.
    """
    try:
        items, total = service.get_diarizations_with_details(
            page=page, limit=limit, step=step, search=search
        )
        status_counts = service.count_by_step()
        total_status_count = sum(status_counts.values()) if status_counts else 0
        total_pages = math.ceil(total / limit) if limit > 0 else 1

        return {
            "items": items,
            "diarizations": items,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "status_counts": status_counts,
            "total_status_count": total_status_count,
        }
    except Exception as e:
        logger.error(f"Failed to fetch diarizations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{id}/reprocess",
    responses={404: {"description": "Diarization task not found"}},
)
@router.post(
    "/{id}/retry",
    responses={404: {"description": "Diarization task not found"}},
)
def reprocess_diarization(
    id: str,
    service: Annotated[DiarizationService, Depends(get_diarization_service)],
):
    """
    Resets a diarization task back to PENDING step for reprocessing.
    Supports either the diarization task UUID or the entity_id (e.g. YouTube video external_id).
    """
    try:
        task = service.reprocess_task(id)
        if not task:
            raise HTTPException(status_code=404, detail="Diarization task not found")

        return {
            "message": f"Diarization task {id} reprocess started (reset to PENDING)",
            "task_id": task.id,
            "entity_id": task.entity_id,
            "step": task.step,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reprocess diarization task {id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{id}/cancel",
    responses={
        404: {"description": "Diarization task not found"},
        409: {"description": "Diarization task is not in a cancellable state"},
    },
)
def cancel_diarization(
    id: str,
    service: Annotated[DiarizationService, Depends(get_diarization_service)],
):
    """
    Cancels a diarization task that is currently in progress.
    Supports either the diarization task UUID or the entity_id (e.g. YouTube video external_id).
    Only tasks with step in [PENDING, STARTED, TRANSCRIPTION, ALIGNMENT, DIARIZATION] can be cancelled.
    After cancellation the step is set to CANCELLED, allowing a new diarization to be triggered.
    """
    try:
        task = service.cancel_task(id)
        if not task:
            raise HTTPException(status_code=404, detail="Diarization task not found")

        if task.step != "CANCELLED":
            raise HTTPException(
                status_code=409,
                detail=f"Diarization task cannot be cancelled (current step: {task.step})",
            )

        return {
            "message": f"Diarization task {id} cancelled successfully",
            "task_id": task.id,
            "entity_id": task.entity_id,
            "step": task.step,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel diarization task {id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

