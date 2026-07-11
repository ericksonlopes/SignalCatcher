from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.application.use_cases.add_content_from_link_use_case import AddContentFromLinkUseCase
from src.application.use_cases.add_content_from_playlist_use_case import AddContentFromPlaylistUseCase
from src.infrastructure.loggers.logger import logger
from src.infrastructure.repositories.content_repository import ContentRepository
from src.infrastructure.services.youtube_scraper import YouTubeScraperService

router = APIRouter()


class YouTubeAddLinkRequest(BaseModel):
    url: str
    origin: str


def get_add_content_use_case() -> AddContentFromLinkUseCase:
    content_repo = ContentRepository(logger=logger)
    scraper = YouTubeScraperService(logger=logger)
    return AddContentFromLinkUseCase(content_repo, scraper, logger)


def get_add_playlist_use_case() -> AddContentFromPlaylistUseCase:
    content_repo = ContentRepository(logger=logger)
    scraper = YouTubeScraperService(logger=logger)
    return AddContentFromPlaylistUseCase(content_repo, scraper, logger)


@router.post("/content")
def add_youtube_content_from_link(request: YouTubeAddLinkRequest,
                                  use_case: AddContentFromLinkUseCase = Depends(get_add_content_use_case)):
    """
    Adds a new content from a given YouTube link.
    It extracts the video metadata (title, channel) and creates a content entity.
    """
    try:
        content = use_case.execute(request.url, request.origin)
        return {"message": "Content added successfully", "content": content}
    except Exception as e:
        logger.error(f"Failed to add YouTube content from link: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/playlist")
def add_youtube_content_from_playlist(request: YouTubeAddLinkRequest,
                                      use_case: AddContentFromPlaylistUseCase = Depends(get_add_playlist_use_case)):
    """
    Adds new content from a given YouTube playlist.
    It extracts metadata from all videos in the playlist and creates content entities.
    """
    try:
        contents = use_case.execute(request.url, request.origin)
        return {"message": f"Successfully added {len(contents)} videos from playlist", "videos_added": len(contents)}
    except Exception as e:
        logger.error(f"Failed to add YouTube content from playlist: {e}")
        raise HTTPException(status_code=400, detail=str(e))
