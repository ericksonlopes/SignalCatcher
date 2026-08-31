from __future__ import annotations

from types import TracebackType
from typing import Callable, Protocol

from sqlalchemy.orm import Session

from src.core.database.connector import Session as DefaultSessionFactory


class IUnitOfWork(Protocol):
    """Transaction boundary for a single business operation.

    Kept dependency-free so use cases can depend on the boundary without knowing
    that SQLAlchemy is the thing implementing it.
    """

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class SqlAlchemyUnitOfWork:
    """Owns one SQLAlchemy session for the duration of one business operation.

    Repositories built with `uow.session` share that session, so a sequence of
    repository calls commits or rolls back as a whole. Previously each repository
    method opened its own session and committed on its own, which made a
    multi-step state transition impossible to keep atomic: a crash midway left the
    row parked in an intermediate step.

    Leaving the block without calling `commit()` discards the work, and any
    exception triggers a rollback before the session is closed.
    """

    def __init__(
        self, session_factory: Callable[[], Session] = DefaultSessionFactory
    ) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.session is only available inside a `with` block."
            )
        return self._session

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            return
        try:
            if exc_type is not None:
                session.rollback()
        finally:
            session.close()
            self._session = None
        # Returning None keeps the original exception propagating.

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
