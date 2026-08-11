import math
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from fastapi import Query

from src.core.logger.logger import logger
from src.modules.youtube.application.use_cases.content.add_content_from_link_use_case import (
    AddContentFromLinkUseCase,
)
from src.modules.youtube.application.use_cases.content.content_commands import (
    ContentCommands,
)
from src.modules.youtube.application.use_cases.content.content_queries import (
    ContentQueries,
)
from src.modules.youtube.presentation.api.dependencies import (
    get_content_commands,
    get_content_queries,
    get_add_content_from_link_use_case,
    get_channel_queries,
)
from src.modules.youtube.application.use_cases.channels.channel_queries import (
    ChannelQueries,
)
from src.modules.youtube.presentation.api.models.requests.youtube_video_add_request import (
    YouTubeVideoAddRequest,
)
from src.modules.youtube.presentation.api.models.responses.paginated_response import (
    PaginatedResponse,
)
from src.modules.youtube.presentation.api.models.responses.step_tracking_response import (
    StepTrackingResponse,
)
from src.modules.youtube.presentation.api.models.responses.youtube_video_card_response import (
    YoutubeVideoCardResponse,
)

router = APIRouter()


from fastapi import BackgroundTasks
from src.modules.youtube.presentation.schedules.jobs.youtube_extract_metadata_job import (
    extract_metadata_job,
)
from src.modules.youtube.presentation.schedules.jobs.youtube_download_job import (
    download_videos_job,
)
from src.modules.youtube.presentation.schedules.jobs.youtube_process_errors_job import (
    process_errors_job,
)


def process_single_video_pipeline():
    try:
        extract_metadata_job()
        download_videos_job()
    except Exception as e:
        logger.error(f"Error in manual video processing pipeline: {e}")


@router.post(
    "/content/retry-errors", responses={500: {"description": "Internal Server Error"}}
)
def retry_error_contents(background_tasks: BackgroundTasks):
    """
    Triggers the background job to retry downloading all videos that are currently in the ERROR step.
    """
    try:
        background_tasks.add_task(process_errors_job)
        return {"message": "Error retry job started in the background."}
    except Exception as e:
        logger.error(f"Failed to trigger error retry job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/content/{external_id}/retry",
    responses={404: {"description": "Content not found"}},
)
def retry_single_content(
    external_id: str,
    background_tasks: BackgroundTasks,
    use_case: Annotated[ContentCommands, Depends(get_content_commands)],
):
    """
    Retries processing a single video by its external ID.
    It sets the video's status to REPROCESSING and runs a dedicated reprocessing pipeline.
    """
    from src.modules.youtube.domain.enums.content_step import ContentStep
    from src.modules.youtube.presentation.schedules.jobs.youtube_process_errors_job import (
        reprocess_single_video_job,
    )

    try:
        success = use_case.set_reprocessing(external_id)
        if not success:
            raise HTTPException(status_code=404, detail="Content not found")

        # Pass the ID to the dedicated reprocessing job
        background_tasks.add_task(reprocess_single_video_job, external_id)

        return {
            "message": f"Retry started for content {external_id}",
            "step": ContentStep.REPROCESSING.name,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry single content {external_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/content/{external_id}", responses={404: {"description": "Content not found"}}
)
def delete_single_content(
    external_id: str,
    use_case: Annotated[ContentCommands, Depends(get_content_commands)],
):
    """
    Sets a video step to DELETED and removes its physical file from the SSD.
    """
    from src.modules.youtube.domain.enums.content_step import ContentStep

    try:
        success = use_case.delete_content(external_id)
        if not success:
            raise HTTPException(status_code=404, detail="Content not found")

        return {
            "message": f"Content {external_id} deleted successfully",
            "step": ContentStep.DELETED.name,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete single content {external_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/content", responses={400: {"description": "Bad Request"}})
def add_youtube_content_from_link(
    request: YouTubeVideoAddRequest,
    background_tasks: BackgroundTasks,
    use_case: Annotated[
        AddContentFromLinkUseCase, Depends(get_add_content_from_link_use_case)
    ],
):
    """
    Adds a new content from a given YouTube link.
    It extracts the video metadata (title, channel) and creates a content entity.
    """
    try:
        content = use_case.execute(request.url)
        background_tasks.add_task(process_single_video_pipeline)
        return {"message": "Content added successfully", "content": content}
    except Exception as e:
        logger.error(f"Failed to add YouTube content from link: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/content/status-count", responses={500: {"description": "Internal Server Error"}}
)
def get_content_status_count(
    use_case: Annotated[ContentQueries, Depends(get_content_queries)],
    channel_use_case: Annotated[ChannelQueries, Depends(get_channel_queries)],
):
    """
    Returns a count of contents grouped by their status, as well as total counts.
    """
    try:
        counts = use_case.get_status_count()
        
        total_videos = sum(counts.values()) if counts else 0
        total_saved_channels = len(channel_use_case.get_saved_channels())
        total_monitored_channels = len(channel_use_case.get_all_channels())
        
        return {
            "status_counts": counts,
            "total_videos": total_videos,
            "total_saved_channels": total_saved_channels,
            "total_monitored_channels": total_monitored_channels
        }
    except Exception as e:
        logger.error(f"Failed to get content status count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/content", response_model=PaginatedResponse[YoutubeVideoCardResponse])
def get_youtube_contents(
    use_case: Annotated[ContentQueries, Depends(get_content_queries)],
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    step: str | None = Query(None, description="Filter by step status"),
    search: str | None = Query(None, description="Search by title"),
):
    """
    Returns a paginated list of YouTube contents.
    """
    try:
        items, total = use_case.get_contents(
            page=page, limit=limit, step=step, search=search
        )

        status_counts = use_case.get_status_count()
        total_status_count = sum(status_counts.values()) if status_counts else 0

        # Mapping to Video Card Response
        mapped_items = [
            YoutubeVideoCardResponse(
                id=item.external_id,
                title=item.title,
                url=item.url,
                channel_name=item.origin,
                step=item.step,
                thumbnail=item.thumbnail,
                duration=item.duration,
                description=(
                    item.raw_metadata.get("description") if item.raw_metadata else None
                ),
                tags=item.tags,
            )
            for item in items
        ]

        total_pages = math.ceil(total / limit)

        return PaginatedResponse[YoutubeVideoCardResponse](
            items=mapped_items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            status_counts=status_counts,
            total_status_count=total_status_count,
        )
    except Exception as e:
        logger.error(f"Failed to get paginated contents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/content/{external_id}/tracking", response_model=list[StepTrackingResponse]
)
def get_content_tracking(
    external_id: str,
    use_case: Annotated[ContentQueries, Depends(get_content_queries)],
):
    """
    Returns the tracking history of a specific YouTube content.
    """
    try:
        trackings = use_case.get_tracking(external_id)
        if trackings is None:
            raise HTTPException(status_code=404, detail="Content not found")

        return [
            StepTrackingResponse(
                id=t.id,
                previous_step=t.previous_step,
                new_step=t.new_step,
                changed_at=t.changed_at,
                details=t.details,
            )
            for t in trackings
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tracking for {external_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
