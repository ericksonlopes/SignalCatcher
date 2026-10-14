from pydantic import BaseModel

from src.modules.diarization.application.dtos.diarization_card_dto import (
    DiarizationCardDTO,
)


class PaginatedDiarizationResponse(BaseModel):
    items: list[DiarizationCardDTO]
    # Same payload under two keys, kept for backwards compatibility with the frontend.
    diarizations: list[DiarizationCardDTO]
    total: int
    page: int
    limit: int
    total_pages: int
    status_counts: dict[str, int] | None = None
    total_status_count: int | None = None
