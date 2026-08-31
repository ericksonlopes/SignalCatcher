import math
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.core.logger.logger import logger
from src.modules.diarization.application.dtos.diarization_card_dto import (
    DiarizationCardDTO,
)
from src.modules.diarization.application.use_cases.diarization_commands import (
    DiarizationCommands,
)
from src.modules.diarization.application.use_cases.diarization_queries import (
    DiarizationQueries,
)
from src.modules.diarization.domain.enums.diarization_step import DiarizationStep
from src.modules.diarization.presentation.api.dependencies import (
    get_diarization_commands,
    get_diarization_queries,
)
from src.modules.youtube.application.use_cases.content.content_queries import (
    ContentQueries,
)
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.presentation.api.dependencies import get_content_queries

router = APIRouter()

# Error detail messages, defined once so the same string is not repeated across the
# handlers.
TASK_NOT_FOUND_DETAIL = "Diarization task not found"
CONTENT_NOT_FOUND_DETAIL = "Content not found"


class DiarizationRequest(BaseModel):
    language: Optional[str] = "en"


class PaginatedDiarizationResponse(BaseModel):
    items: List[DiarizationCardDTO]
    # Same payload under two keys, kept for backwards compatibility with the frontend.
    diarizations: List[DiarizationCardDTO]
    total: int
    page: int
    limit: int
    total_pages: int
    status_counts: Optional[dict[str, int]] = None
    total_status_count: Optional[int] = None


@router.post(
    "/youtube/{external_id}",
    responses={
        404: {"description": "Content not found"},
        400: {"description": "Bad Request"},
        500: {"description": "Internal server error"},
    },
)
def trigger_youtube_diarization(
    external_id: str,
    request: DiarizationRequest,
    commands: Annotated[DiarizationCommands, Depends(get_diarization_commands)],
    queries: Annotated[ContentQueries, Depends(get_content_queries)],
):
    """
    Creates a diarization task for a completed YouTube content.
    """
    try:
        # The content is read through the youtube module's own provider, so this route
        # no longer builds that module's repository and session by hand.
        content = queries.get_content_by_external_id(external_id)
        if not content:
            raise HTTPException(status_code=404, detail=CONTENT_NOT_FOUND_DETAIL)

        if (
            content.step != ContentStep.COMPLETED.name
            and content.step != ContentStep.COMPLETED
        ):
            raise HTTPException(
                status_code=400, detail="Content must be completed to diarize"
            )

        if not content.file_path:
            raise HTTPException(status_code=400, detail="Content file path is missing")

        task = commands.create_task(
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
    queries: Annotated[DiarizationQueries, Depends(get_diarization_queries)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    step: Annotated[Optional[str], Query(description="Filter by step status")] = None,
    search: Annotated[
        Optional[str], Query(description="Search by title or channel")
    ] = None,
):
    """
    Returns a paginated list of diarizations enriched with YouTube content details.
    """
    try:
        items, total = queries.get_cards(
            page=page, limit=limit, step=step, search=search
        )
        status_counts = queries.count_by_step()
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
    responses={
        404: {"description": "Diarization task not found"},
        500: {"description": "Internal server error"},
    },
)
@router.post(
    "/{id}/retry",
    responses={
        404: {"description": "Diarization task not found"},
        500: {"description": "Internal server error"},
    },
)
def reprocess_diarization(
    id: str,
    commands: Annotated[DiarizationCommands, Depends(get_diarization_commands)],
):
    """
    Resets a diarization task back to PENDING step for reprocessing.
    Supports either the diarization task UUID or the entity_id (e.g. YouTube video external_id).
    """
    try:
        task = commands.reprocess_task(id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_DETAIL)

        return {
            "message": f"Diarization task {id} reprocess started (reset to PENDING)",
            "task_id": task.id,
            "entity_id": task.entity_id,
            "step": task.step.value,
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
        500: {"description": "Internal server error"},
    },
)
def cancel_diarization(
    id: str,
    commands: Annotated[DiarizationCommands, Depends(get_diarization_commands)],
):
    """
    Cancels a diarization task that is currently in progress.
    Supports either the diarization task UUID or the entity_id (e.g. YouTube video external_id).
    Only tasks with step in [PENDING, STARTED, TRANSCRIPTION, ALIGNMENT, DIARIZATION] can be cancelled.
    After cancellation the step is set to CANCELLED, allowing a new diarization to be triggered.
    """
    try:
        task = commands.cancel_task(id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_DETAIL)

        if task.step is not DiarizationStep.CANCELLED:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Diarization task cannot be cancelled "
                    f"(current step: {task.step.value})"
                ),
            )

        return {
            "message": f"Diarization task {id} cancelled successfully",
            "task_id": task.id,
            "entity_id": task.entity_id,
            "step": task.step.value,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel diarization task {id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
