from __future__ import annotations

from types import TracebackType
from typing import Protocol

from src.modules.youtube.domain.interfaces.repositories.youtube_channel_repository import (
    IYouTubeChannelRepository,
)
from src.modules.youtube.domain.interfaces.repositories.youtube_monitored_channel_repository import (
    IYouTubeMonitoredChannelRepository,
)
from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)


class IYoutubeUnitOfWork(Protocol):
    """Transaction boundary that exposes the YouTube collaborators bound to it.

    Use cases enter the block, operate through the collaborators, and call `commit()`
    once the whole operation is consistent. Leaving the block without committing
    discards the changes, so a crash midway cannot leave a row parked in an
    intermediate step.

    The session lives behind this contract on purpose: the application layer never
    sees SQLAlchemy.
    """

    contents: IYoutubeContentService
    monitored_channels: IYouTubeMonitoredChannelRepository
    channels: IYouTubeChannelRepository

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def __enter__(self) -> IYoutubeUnitOfWork: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
