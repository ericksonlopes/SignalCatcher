from src.modules.voice_recognition.domain.interfaces.repositories.speaker_repository_interface import (  # noqa: E501
    ISpeakerRepository,
)
from src.modules.voice_recognition.domain.interfaces.services.voice_embedding_service_interface import (  # noqa: E501
    IVoiceEmbeddingService,
)

__all__ = ["ISpeakerRepository", "IVoiceEmbeddingService"]
