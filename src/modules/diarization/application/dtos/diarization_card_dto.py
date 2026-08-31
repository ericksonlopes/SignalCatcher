from typing import Any, Optional

from pydantic import BaseModel

# Presentation defaults for a diarization whose linked content is missing. These used to
# be inlined in the repository, which put a Portuguese UI label and a stock-photo URL in
# the persistence layer.
UNKNOWN_LABEL = "Desconhecido"
PLACEHOLDER_THUMBNAIL = (
    "https://images.unsplash.com/photo-1590602847861-f357a9332bbc"
    "?w=300&auto=format&fit=crop&q=80"
)
UNKNOWN_DURATION = "00:00:00"


class DiarizationCardDTO(BaseModel):
    """A diarization enriched with the details of the content it came from.

    Field names match what the frontend already consumes, including the camelCase
    `channelName`, so the JSON contract is unchanged.
    """

    id: str
    step: str
    created_at: Optional[str] = None
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    title: str = UNKNOWN_LABEL
    channelName: str = UNKNOWN_LABEL  # noqa: N815 - matches the existing API contract
    thumbnail: str = PLACEHOLDER_THUMBNAIL
    duration: str = UNKNOWN_DURATION
    result_json: Optional[Any] = None
