from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from src.core.database.connector import Session as DefaultSessionFactory
from src.core.database.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.diarization.infrastructure.repositories.diarization_repository import (
    DiarizationRepository,
)
from src.modules.voice_recognition.domain.interfaces import ISpeakerRepository
from src.modules.voice_recognition.infrastructure.repositories.speaker_repository import (
    SpeakerRepository,
)


class VoiceRecognitionUnitOfWork(SqlAlchemyUnitOfWork):
    """Wires speaker and diarization repositories onto a single transaction."""

    speakers: ISpeakerRepository
    diarizations: IDiarizationRepository

    def __init__(self, session_factory: Callable[[], Session] = DefaultSessionFactory) -> None:
        super().__init__(session_factory=session_factory)

    def __enter__(self) -> VoiceRecognitionUnitOfWork:
        super().__enter__()
        self.speakers = SpeakerRepository(session=self.session)
        self.diarizations = DiarizationRepository(session=self.session)
        return self
