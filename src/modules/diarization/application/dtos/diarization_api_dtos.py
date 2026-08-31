from typing import List, Optional

from pydantic import BaseModel, Field


class DiarizationPathRequest(BaseModel):
    audio_path: str = Field(
        ...,
        description="Caminho absoluto ou relativo para o arquivo de áudio no servidor.",
    )
    language: Optional[str] = Field(
        None, description="Código do idioma (ex: 'pt', 'en')."
    )
    num_speakers: Optional[int] = Field(
        None, ge=1, description="Número exato de falantes no áudio."
    )
    min_speakers: Optional[int] = Field(
        None, ge=1, description="Número mínimo de falantes."
    )
    max_speakers: Optional[int] = Field(
        None, ge=1, description="Número máximo de falantes."
    )
    model_size: str = Field("large-v2", description="Tamanho do modelo Whisper.")


class SegmentDto(BaseModel):
    speaker: str
    start: float
    end: float
    text: str


class DiarizationResponse(BaseModel):
    audio_path: str
    language: str
    duration: float
    speakers: List[str]
    segments: List[SegmentDto]
