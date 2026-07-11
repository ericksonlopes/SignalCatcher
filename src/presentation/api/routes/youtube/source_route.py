from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.dtos.source_create_dto import SourceCreateDTO
from src.application.dtos.source_response_dto import SourceResponseDTO
from src.application.dtos.youtube_source_create_dto import YouTubeSourceCreateDTO
from src.application.use_cases.create_source_use_case import CreateSourceUseCase
from src.domain.models.enums.source_platform import SourcePlatform
from src.presentation.api.dependencies import get_create_source_use_case

router = APIRouter()


@router.post("/sources", response_model=SourceResponseDTO, status_code=status.HTTP_201_CREATED)
def create_youtube_source(source_data: YouTubeSourceCreateDTO,
                          use_case: Annotated[CreateSourceUseCase, Depends(get_create_source_use_case)]):
    """
    Registers a new YouTube Channel to be monitored.
    """
    try:
        full_data = SourceCreateDTO(
            name=source_data.name,
            url=source_data.url,
            source_platform=SourcePlatform.YOUTUBE
        )
        return use_case.execute(full_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
