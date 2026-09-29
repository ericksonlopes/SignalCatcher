import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.database.job_control import JobControlRepository
from src.core.logger.logger import logger
from src.modules.diarization.application.use_cases.diarization_queries import DiarizationQueries
from src.modules.diarization.presentation.api.dependencies import get_diarization_queries
from src.modules.youtube.application.use_cases.channels.channel_queries import ChannelQueries
from src.modules.youtube.application.use_cases.content.add_content_from_link_use_case import (
    AddContentFromLinkUseCase,
)
from src.modules.youtube.application.use_cases.content.content_commands import ContentCommands
from src.modules.youtube.application.use_cases.content.content_queries import ContentQueries
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.processing import ContentBusyError
from src.modules.youtube.presentation.api.dependencies import (
    get_add_content_from_link_use_case,
    get_channel_queries,
    get_content_commands,
    get_content_queries,
    get_job_control,
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
CONTENT_NOT_FOUND_DETAIL = "Content not found"
JobControl = Annotated[JobControlRepository, Depends(get_job_control)]


@router.post("/content/retry-errors", status_code=202)
def retry_error_contents(control: JobControl):
    control.request("youtube_process_errors")
    return {"message": "Error retry request queued."}


@router.post("/content/trigger-metadata-extraction", status_code=202)
def trigger_metadata_extraction(control: JobControl):
    control.request("youtube_extract_metadata")
    return {"message": "Metadata extraction request queued."}


@router.post("/content/trigger-downloads", status_code=202)
def trigger_downloads(control: JobControl):
    control.request("youtube_download_videos")
    return {"message": "Download request queued."}


@router.post("/content/{external_id}/retry", status_code=202)
def retry_single_content(
    external_id: str,
    use_case: Annotated[ContentCommands, Depends(get_content_commands)],
    control: JobControl,
):
    try:
        if not use_case.set_reprocessing(external_id):
            raise HTTPException(404, CONTENT_NOT_FOUND_DETAIL)
        control.request("youtube_process_errors")
        return {"message": "Retry queued.", "step": ContentStep.REPROCESSING.name}
    except ContentBusyError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete("/content/{external_id}", status_code=202)
def delete_single_content(
    external_id: str,
    use_case: Annotated[ContentCommands, Depends(get_content_commands)],
    control: JobControl,
):
    try:
        if not use_case.delete_content(external_id):
            raise HTTPException(404, CONTENT_NOT_FOUND_DETAIL)
        control.request("youtube_delete_contents")
        return {"message": "File deletion queued.", "deletion_requested": True}
    except ContentBusyError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/content")
def add_youtube_content_from_link(
    request: YouTubeVideoAddRequest,
    use_case: Annotated[AddContentFromLinkUseCase, Depends(get_add_content_from_link_use_case)],
    control: JobControl,
):
    try:
        content = use_case.execute(request.url)
        control.request("youtube_extract_and_download")
        return {"message": "Content added successfully", "content": content}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get(
    "/content/status-count",
    responses={500: {"description": "Internal Server Error"}},
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
            "total_monitored_channels": total_monitored_channels,
        }
    except Exception as e:
        logger.error(f"Failed to get content status count: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get(
    "/content",
    response_model=PaginatedResponse[YoutubeVideoCardResponse],
    responses={500: {"description": "Internal Server Error"}},
)
def get_youtube_contents(
    use_case: Annotated[ContentQueries, Depends(get_content_queries)],
    diarization: Annotated[DiarizationQueries, Depends(get_diarization_queries)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    step: Annotated[str | None, Query(description="Filter by step status")] = None,
    search: Annotated[str | None, Query(description="Search by title")] = None,
    channel: Annotated[str | None, Query(description="Filter by channel/origin name")] = None,
):
    """
    Returns a paginated list of YouTube contents.
    """
    try:
        items, total = use_case.get_contents(
            page=page, limit=limit, step=step, search=search, channel=channel
        )

        status_counts = use_case.get_status_count()
        total_status_count = sum(status_counts.values()) if status_counts else 0

        # Fetch diarization statuses for returned items. The lookup is best-effort:
        # a failure here degrades the cards instead of failing the whole listing.
        external_ids = [item.external_id for item in items if item.external_id]
        diarization_map = {}
        if external_ids:
            try:
                diarization_map = diarization.get_steps_by_entity_ids(external_ids)
            except Exception as ex:
                logger.warning(f"Could not fetch diarization statuses: {ex}")

        # Mapping to Video Card Response
        mapped_items = []
        for item in items:
            d_status = diarization_map.get(item.external_id)
            mapped_items.append(
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
                    file_path=item.file_path,
                    language=item.language,
                    created_at=item.created_at,
                    published_at=item.published_at,
                    deletion_requested=item.deletion_requested,
                    attempt_count=item.attempt_count,
                    next_retry_at=item.next_retry_at,
                    error_info=item.error_info,
                    is_diarized=(d_status == "COMPLETED"),
                    diarization_status=d_status,
                )
            )

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
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get(
    "/content/{external_id}/tracking",
    response_model=list[StepTrackingResponse],
    responses={
        404: {"description": "Content not found"},
        500: {"description": "Internal Server Error"},
    },
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
            raise HTTPException(status_code=404, detail=CONTENT_NOT_FOUND_DETAIL)

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
        raise HTTPException(status_code=500, detail="Internal Server Error")
