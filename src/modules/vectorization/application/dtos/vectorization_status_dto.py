from pydantic import BaseModel


class VectorizationStatusDTO(BaseModel):
    diarization_id: str
    content_id: str | None = None
    chunks_count: int
    indexed: bool


class VectorizationStatsDTO(BaseModel):
    total_chunks: int
    total_indexed_diarizations: int
    tei_healthy: bool
