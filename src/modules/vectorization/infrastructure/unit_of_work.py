from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from src.core.database.connector import Session as DefaultSessionFactory
from src.core.database.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.vectorization.domain.interfaces.repositories.chunk_repository_interface import (
    IChunkRepository,
)
from src.modules.vectorization.infrastructure.repositories.chunk_repository import (
    ChunkRepository,
)


class VectorizationUnitOfWork(SqlAlchemyUnitOfWork):
    """Wires the chunk repository onto a single session for one operation."""

    chunks: IChunkRepository

    def __init__(
        self, session_factory: Callable[[], Session] = DefaultSessionFactory
    ) -> None:
        super().__init__(session_factory=session_factory)

    def __enter__(self) -> VectorizationUnitOfWork:
        super().__enter__()
        self.chunks = ChunkRepository(session=self.session)
        return self
