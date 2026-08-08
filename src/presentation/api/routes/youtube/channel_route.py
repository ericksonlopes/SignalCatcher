from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.dtos.channel_create_dto import ChannelCreateDTO
from src.application.dtos.youtube_channel_response_dto import YouTubeChannelResponseDTO
from src.application.dtos.youtube_channel_create_dto import YouTubeChannelCreateDTO
from src.application.use_cases.channels_use_case import ChannelsUseCase
from src.presentation.api.dependencies import get_channels_use_case

router = APIRouter()


@router.post("/channels", response_model=YouTubeChannelResponseDTO, status_code=status.HTTP_201_CREATED, responses={status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"}})
def create_youtube_channel(channel_data: YouTubeChannelCreateDTO,
                          use_case: Annotated[ChannelsUseCase, Depends(get_channels_use_case)]):
    """
    Registers a new YouTube Channel to be monitored.
    """
    try:
        full_data = ChannelCreateDTO(
            name=channel_data.name,
            url=channel_data.url
        )
        return use_case.create_channel(full_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/channels", response_model=list[YouTubeChannelResponseDTO])
def get_channels(
    use_case: Annotated[ChannelsUseCase, Depends(get_channels_use_case)]
):
    """
    Returns a list of all monitored channels.
    """
    try:
        return use_case.get_all_channels()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.patch("/channels/{channel_id}/status", response_model=YouTubeChannelResponseDTO)
def toggle_channel_status(
    channel_id: int,
    use_case: Annotated[ChannelsUseCase, Depends(get_channels_use_case)]
):
    """
    Toggles the active status of a channel.
    """
    try:
        return use_case.toggle_channel_status(channel_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
