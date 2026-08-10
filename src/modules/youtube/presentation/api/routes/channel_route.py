from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.modules.youtube.application.dtos.channel_create_dto import ChannelCreateDTO
from src.modules.youtube.application.dtos.youtube_channel_create_dto import (
    YouTubeChannelCreateDTO,
)
from src.modules.youtube.application.dtos.youtube_channel_response_dto import (
    YouTubeChannelResponseDTO,
)
from src.modules.youtube.application.use_cases.channels.channel_commands import (
    ChannelCommands,
)
from src.modules.youtube.application.use_cases.channels.channel_queries import (
    ChannelQueries,
)
from src.modules.youtube.presentation.api.dependencies import (
    get_channel_commands,
    get_channel_queries,
)

router = APIRouter()


@router.post(
    "/monitored_channels",
    response_model=YouTubeChannelResponseDTO,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"}},
)
def create_youtube_channel(
    channel_data: YouTubeChannelCreateDTO,
    use_case: Annotated[ChannelCommands, Depends(get_channel_commands)],
):
    """
    Registers a new YouTube Channel to be monitored.
    """
    try:
        full_data = ChannelCreateDTO(name=channel_data.name, url=channel_data.url)
        return use_case.create_channel(full_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/monitored_channels", response_model=list[YouTubeChannelResponseDTO])
def get_all_channels(use_case: Annotated[ChannelQueries, Depends(get_channel_queries)]):
    """
    Returns a list of all monitored channels.
    """
    try:
        return use_case.get_all_channels()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


from src.modules.youtube.application.dtos.saved_youtube_channel_response_dto import (
    SavedYouTubeChannelResponseDTO,
)


@router.get("/channels", response_model=list[SavedYouTubeChannelResponseDTO])
def get_saved_channels(
    use_case: Annotated[ChannelQueries, Depends(get_channel_queries)],
):
    """
    Returns a list of all saved youtube channels.
    """
    try:
        return use_case.get_saved_channels()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.patch(
    "/monitored_channels/{channel_id}/status", response_model=YouTubeChannelResponseDTO
)
def toggle_channel_status(
    channel_id: int, use_case: Annotated[ChannelCommands, Depends(get_channel_commands)]
):
    """
    Toggles the active status of a channel.
    """
    try:
        return use_case.toggle_channel_status(channel_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
