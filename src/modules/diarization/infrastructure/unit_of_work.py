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


class DiarizationUnitOfWork(SqlAlchemyUnitOfWork):
    """Wires the diarization repository onto a single session for one operation."""

    # Declared as the interface: the protocol attribute is mutable and therefore
    # invariant, so a narrower type would not satisfy it.
    diarizations: IDiarizationRepository

    def __init__(
        self, session_factory: Callable[[], Session] = DefaultSessionFactory
    ) -> None:
        super().__init__(session_factory=session_factory)

    def __enter__(self) -> DiarizationUnitOfWork:
        super().__enter__()
        self.diarizations = DiarizationRepository(session=self.session)
        return self
