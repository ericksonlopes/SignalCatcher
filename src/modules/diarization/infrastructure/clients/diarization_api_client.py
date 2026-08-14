import logging
from typing import BinaryIO
import requests
from requests.exceptions import RequestException

from src.core.config.settings import settings
from src.modules.diarization.application.dtos import DiarizationPathRequest, DiarizationResponse
from src.modules.diarization.domain.interfaces.diarization_client_interface import IDiarizationClient

logger = logging.getLogger(__name__)


class DiarizationApiClient(IDiarizationClient):
    def __init__(self):
        self.base_url = settings.DIARIZATION_API_URL
        if not self.base_url:
            raise ValueError("DIARIZATION_API_URL não está configurada em settings.py.")

    def process_by_path(self, request: DiarizationPathRequest) -> DiarizationResponse:
        url = f"{self.base_url.rstrip('/')}/api/diarization/process-path"
        logger.info(f"Enviando requisição de diarização por path para: {url}")
        
        try:
            response = requests.post(url, json=request.model_dump(exclude_none=True))
            response.raise_for_status()
            data = response.json()
            return DiarizationResponse(**data)
        except RequestException as e:
            logger.error(f"Erro na requisição à API de Diarização: {e}")
            raise Exception(f"Falha ao comunicar com a API de diarização: {e}")

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
        url = f"{self.base_url.rstrip('/')}/api/diarization/process-file"
        logger.info(f"Enviando requisição de diarização por arquivo para: {url}")
        
        files = {
            "file": (filename, file_obj, "audio/wav")
        }
        data = {
            "model_size": model_size
        }
        if language:
            data["language"] = language
        if num_speakers:
            data["num_speakers"] = num_speakers
        if min_speakers:
            data["min_speakers"] = min_speakers
        if max_speakers:
            data["max_speakers"] = max_speakers

        try:
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            response_data = response.json()
            return DiarizationResponse(**response_data)
        except RequestException as e:
            logger.error(f"Erro no upload para a API de Diarização: {e}")
            raise Exception(f"Falha no upload para a API de diarização: {e}")
