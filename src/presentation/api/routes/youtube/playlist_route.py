from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends

from src.application.use_cases.add_content_from_playlist_use_case import AddContentFromPlaylistUseCase
from src.infrastructure.loggers.logger import logger
from src.infrastructure.repositories.content_repository import ContentRepository
from src.infrastructure.services.youtube_scraper import YouTubeScraperService
from src.presentation.api.models.requests.youtube_playlist_add_request import YouTubePlaylistAddRequest

router = APIRouter()


def get_add_playlist_use_case() -> AddContentFromPlaylistUseCase:
    content_repo = ContentRepository(logger=logger)
    scraper = YouTubeScraperService(logger=logger)
    return AddContentFromPlaylistUseCase(content_repo, scraper, logger)


@router.post("/playlist")
def add_youtube_content_from_playlist(request: YouTubePlaylistAddRequest,
                                      use_case: Annotated[AddContentFromPlaylistUseCase, Depends(get_add_playlist_use_case)]):
    """
    Adds new content from a given YouTube playlist.
    It extracts metadata from all videos in the playlist and creates content entities.
    """
    try:
        contents = use_case.execute(request.url, request.save_in_playlist_folder)
        return {"message": f"Successfully added {len(contents)} videos from playlist", "videos_added": len(contents)}
    except Exception as e:
        logger.error(f"Failed to add YouTube content from playlist: {e}")
        raise HTTPException(status_code=400, detail=str(e))
