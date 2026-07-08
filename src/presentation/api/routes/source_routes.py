from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.dtos.source_create_dto import SourceCreateDTO
from src.application.dtos.source_response_dto import SourceResponseDTO
from src.application.use_cases.create_source_use_case import CreateSourceUseCase
from src.presentation.api.dependencies import get_create_source_use_case

router = APIRouter()


@router.post("/", response_model=SourceResponseDTO, status_code=status.HTTP_201_CREATED)
def create_source(source_data: SourceCreateDTO, use_case: Annotated[CreateSourceUseCase, Depends(get_create_source_use_case)]):
    """
    Registers a new content source (e.g., YouTube Channel) to be monitored.
    """
    try:
        return use_case.execute(source_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
