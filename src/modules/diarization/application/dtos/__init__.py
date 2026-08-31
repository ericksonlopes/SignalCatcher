"""DTOs for the diarization module.

`dtos` used to be a single module. It became a package, so the names it exported are
re-exported here to keep existing imports working.
"""

from src.modules.diarization.application.dtos.diarization_api_dtos import (
    DiarizationPathRequest,
    DiarizationResponse,
    SegmentDto,
)
from src.modules.diarization.application.dtos.diarization_card_dto import (
    DiarizationCardDTO,
)

__all__ = [
    "DiarizationCardDTO",
    "DiarizationPathRequest",
    "DiarizationResponse",
    "SegmentDto",
]
