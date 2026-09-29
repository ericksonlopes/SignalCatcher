from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.core.database.job_control import JobControlRepository
from src.core.logger.logger import logger
from src.modules.youtube.application.use_cases.content.add_content_from_playlist_use_case import (
    AddContentFromPlaylistUseCase,
)
from src.modules.youtube.presentation.api.dependencies import (
    get_add_content_from_playlist_use_case,
    get_job_control,
)
from src.modules.youtube.presentation.api.models.requests.youtube_playlist_add_request import (
    YouTubePlaylistAddRequest,
)

router = APIRouter()


@router.post("/playlist", responses={400: {"description": "Bad Request"}})
def add_youtube_content_from_playlist(
    request: YouTubePlaylistAddRequest,
    control: Annotated[JobControlRepository, Depends(get_job_control)],
    use_case: Annotated[
        AddContentFromPlaylistUseCase, Depends(get_add_content_from_playlist_use_case)
    ],
):
    """
    Adds new content from a given YouTube playlist.
    It extracts metadata from all videos in the playlist and creates content entities.
    """
    try:
        contents = use_case.execute(request.url, request.save_in_playlist_folder)
        if contents:
            control.request("youtube_extract_and_download")
        return {
            "message": f"Successfully added {len(contents)} videos from playlist",
            "videos_added": len(contents),
        }
    except Exception as e:
        logger.error(f"Failed to add YouTube content from playlist: {e}")
        raise HTTPException(status_code=400, detail=str(e))
