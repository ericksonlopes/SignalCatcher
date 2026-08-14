from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends

from src.core.logger.logger import logger
from src.modules.diarization.infrastructure.services.diarization_service import (
    DiarizationService,
)

router = APIRouter()


def get_diarization_service():
    return DiarizationService()


from pydantic import BaseModel
from typing import Optional

class DiarizationRequest(BaseModel):
    language: Optional[str] = None

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
            entity_type="YOUTUBE_VIDEO",
            language=request.language,
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
    responses={500: {"description": "Internal server error"}},
)
def get_diarizations(
    service: Annotated[DiarizationService, Depends(get_diarization_service)],
):
    """
    Returns all diarizations enriched with YouTube content details.
    """
    try:
        diarizations = service.get_diarizations_with_details()
        return {"diarizations": diarizations}
    except Exception as e:
        logger.error(f"Failed to fetch diarizations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
