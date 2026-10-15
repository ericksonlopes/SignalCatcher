from pydantic import BaseModel, Field


class SemanticSearchQueryDTO(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    limit: int = Field(default=10, ge=1, le=100)
    min_similarity: float = Field(default=0.4, ge=0.0, le=1.0)
    source_type: str | None = None
    parent_id: str | None = None
    speaker: str | None = None
