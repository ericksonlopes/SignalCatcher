from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends

from src.application.use_cases.add_content_from_link_use_case import AddContentFromLinkUseCase
from src.config.settings import settings
from src.infrastructure.loggers.logger import logger
from src.infrastructure.notifications.voice_monkey_notification import VoiceMonkeyNotification
from src.infrastructure.repositories.youtube_content_repository import (
    YoutubeContentRepository,
)
from src.infrastructure.services.youtube_scraper import YouTubeScraperService
from src.presentation.api.models.requests.youtube_video_add_request import YouTubeVideoAddRequest
from src.presentation.api.models.responses.paginated_response import PaginatedResponse
from src.presentation.api.models.responses.youtube_video_card_response import YoutubeVideoCardResponse
import math
from fastapi import Query

from src.presentation.api.models.responses.content_tracking_response import ContentTrackingResponse

router = APIRouter()


def get_add_content_use_case() -> AddContentFromLinkUseCase:
    content_repo = YoutubeContentRepository(logger=logger)
    scraper = YouTubeScraperService(logger=logger)
    notification = VoiceMonkeyNotification(
        api_token=settings.VOICE_MONKEY_API_TOKEN,
        monkey_id=settings.VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID,
        logger=logger
    )
    return AddContentFromLinkUseCase(content_repo, scraper, notification, logger)


from fastapi import BackgroundTasks
from src.presentation.schedules.jobs.youtube_extract_metadata_job import extract_metadata_job

@router.post("/content", responses={400: {"description": "Bad Request"}})
def add_youtube_content_from_link(request: YouTubeVideoAddRequest,
                                  background_tasks: BackgroundTasks,
                                  use_case: Annotated[AddContentFromLinkUseCase, Depends(get_add_content_use_case)]):
    """
    Adds a new content from a given YouTube link.
    It extracts the video metadata (title, channel) and creates a content entity.
    """
    try:
        content = use_case.execute(request.url)
        background_tasks.add_task(extract_metadata_job)
        return {"message": "Content added successfully", "content": content}
    except Exception as e:
        logger.error(f"Failed to add YouTube content from link: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/content/status-count", responses={500: {"description": "Internal Server Error"}})
def get_content_status_count(
    repo: Annotated[
        YoutubeContentRepository,
        Depends(lambda: YoutubeContentRepository(logger=logger)),
    ],
):
    """
    Returns a count of contents grouped by their status.
    """
    try:
        counts = repo.count_by_step()
        return {"status_counts": counts}
    except Exception as e:
        logger.error(f"Failed to get content status count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/content", response_model=PaginatedResponse[YoutubeVideoCardResponse])
def get_youtube_contents(
    repo: Annotated[
        YoutubeContentRepository,
        Depends(lambda: YoutubeContentRepository(logger=logger)),
    ],
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Returns a paginated list of YouTube contents.
    """
    try:
        items, total = repo.get_paginated(page=page, limit=limit)
        
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
                description=item.raw_metadata.get("description") if item.raw_metadata else None,
                tags=item.tags
            ) for item in items
        ]
        
        total_pages = math.ceil(total / limit)
        
        return PaginatedResponse[YoutubeVideoCardResponse](
            items=mapped_items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages
        )
    except Exception as e:
        logger.error(f"Failed to get paginated contents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/content/{external_id}/tracking", response_model=list[ContentTrackingResponse])
def get_content_tracking(
    external_id: str,
    repo: Annotated[
        YoutubeContentRepository,
        Depends(lambda: YoutubeContentRepository(logger=logger)),
    ]
):
    """
    Returns the tracking history of a specific YouTube content.
    """
    try:
        if not repo.exists_by_external_id(external_id):
            raise HTTPException(status_code=404, detail="Content not found")
            
        trackings = repo.get_tracking_by_external_id(external_id)
        
        return [
            ContentTrackingResponse(
                id=t.id,
                previous_step=t.previous_step,
                new_step=t.new_step,
                changed_at=t.changed_at,
                details=t.details
            ) for t in trackings
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tracking for {external_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

