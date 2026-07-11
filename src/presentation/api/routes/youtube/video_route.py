from fastapi import APIRouter, HTTPException, Depends

from src.application.use_cases.add_content_from_link_use_case import AddContentFromLinkUseCase
from src.infrastructure.loggers.logger import logger
from src.infrastructure.repositories.content_repository import ContentRepository
from src.infrastructure.services.youtube_scraper import YouTubeScraperService
from src.presentation.api.models.requests.youtube_video_add_request import YouTubeVideoAddRequest

router = APIRouter()


def get_add_content_use_case() -> AddContentFromLinkUseCase:
    content_repo = ContentRepository(logger=logger)
    scraper = YouTubeScraperService(logger=logger)
    return AddContentFromLinkUseCase(content_repo, scraper, logger)


@router.post("/content")
def add_youtube_content_from_link(request: YouTubeVideoAddRequest,
                                  use_case: AddContentFromLinkUseCase = Depends(get_add_content_use_case)):
    """
    Adds a new content from a given YouTube link.
    It extracts the video metadata (title, channel) and creates a content entity.
    """
    try:
        content = use_case.execute(request.url)
        return {"message": "Content added successfully", "content": content}
    except Exception as e:
        logger.error(f"Failed to add YouTube content from link: {e}")
        raise HTTPException(status_code=400, detail=str(e))
