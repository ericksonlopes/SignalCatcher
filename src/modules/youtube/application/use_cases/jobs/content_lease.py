from collections.abc import Callable
from datetime import datetime, timezone
from threading import Event, Thread
from time import monotonic
from types import TracebackType

from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.entities.youtube_content_entity import YoutubeContentEntity
from src.modules.youtube.domain.interfaces.unit_of_work import IYoutubeUnitOfWork
from src.modules.youtube.domain.processing import LeaseLostError


class ContentLease:
    """Renew a reservation in short transactions while external work is running."""

    def __init__(
        self,
        uow_factory: Callable[[], IYoutubeUnitOfWork],
        content: YoutubeContentEntity,
        logger: ILogger,
    ):
        self.uow_factory = uow_factory
        self.external_id = content.external_id
        token = content.lease_token
        if not token:
            raise LeaseLostError("A reservation is required to process content.")
        self.token: str = token
        if content.lease_expires_at is None:
            raise LeaseLostError("A reservation expiry is required.")
        self.ttl = (content.lease_expires_at - datetime.now(timezone.utc)).total_seconds()
        self.deadline = monotonic() + self.ttl
        self.logger = logger
        self.stopped = Event()
        self.lost = Event()
        self.thread = Thread(target=self._heartbeat, daemon=True)

    def _heartbeat(self) -> None:
        while not self.stopped.wait(20):
            try:
                with self.uow_factory() as uow:
                    valid = uow.contents.renew_lease(self.external_id, self.token)
                    uow.commit()
                if not valid:
                    self.lost.set()
                    return
                self.deadline = monotonic() + self.ttl
            except Exception as exc:
                self.logger.error(f"Lease heartbeat failed for {self.external_id}: {exc}")
                self.lost.set()
                return

    def ensure_owned(self) -> None:
        if self.lost.is_set() or monotonic() >= self.deadline:
            raise LeaseLostError("Content reservation heartbeat was lost.")

    def __enter__(self) -> "ContentLease":
        self.thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stopped.set()
        self.thread.join(timeout=5)
        with self.uow_factory() as uow:
            uow.contents.release_lease(self.external_id, self.token)
            uow.commit()
