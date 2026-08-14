from abc import ABC, abstractmethod
from typing import BinaryIO

from src.modules.diarization.application.dtos import DiarizationPathRequest, DiarizationResponse


class IDiarizationClient(ABC):
    @abstractmethod
    def process_by_path(self, request: DiarizationPathRequest) -> DiarizationResponse:
        """Envia um request de diarização fornecendo o caminho absoluto no servidor da API."""
        pass

    @abstractmethod
    def process_by_file(
        self,
        file_obj: BinaryIO,
        filename: str,
        language: str | None = None,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        model_size: str = "large-v2"
    ) -> DiarizationResponse:
        """Faz o upload de um arquivo para a API de diarização."""
        pass
