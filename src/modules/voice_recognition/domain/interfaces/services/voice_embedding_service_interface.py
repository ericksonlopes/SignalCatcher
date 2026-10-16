from abc import ABC, abstractmethod
from typing import Any


class IVoiceEmbeddingService(ABC):
    @abstractmethod
    def extract_embedding_from_segments(
        self,
        file_path: str,
        segments: list[dict[str, Any]],
    ) -> list[float]:
        """Extracts a normalized voiceprint embedding vector from specific audio segments."""
        pass

    @abstractmethod
    def extract_speakers_embeddings(
        self,
        file_path: str,
        segments_by_speaker: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[float]]:
        """Extracts normalized voiceprint embeddings for multiple speakers in a single pass."""
        pass

    @abstractmethod
    def extract_embedding_from_bytes(
        self,
        audio_bytes: bytes,
        filename: str = "sample.wav",
    ) -> list[float]:
        """Extracts a normalized voiceprint embedding vector from raw uploaded audio bytes."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Checks if the voice embedding extractor is operational."""
        pass
