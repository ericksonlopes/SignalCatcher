from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from src.core.database.connector import Session as DefaultSessionFactory
from src.core.database.unit_of_work import SqlAlchemyUnitOfWork
from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.interfaces.repositories.youtube_channel_repository import (
    IYouTubeChannelRepository,
)
from src.modules.youtube.domain.interfaces.repositories.youtube_monitored_channel_repository import (
    IYouTubeMonitoredChannelRepository,
)
from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)
from src.modules.youtube.infrastructure.repositories.youtube_channel_repository import (
    YouTubeChannelRepository,
)
from src.modules.youtube.infrastructure.repositories.youtube_content_repository import (
    YoutubeContentRepository,
)
from src.modules.youtube.infrastructure.repositories.youtube_monitored_channel_repository import (
    YouTubeMonitoredChannelRepository,
)
from src.modules.youtube.infrastructure.services.youtube_content_service import (
    YoutubeContentService,
)


class YoutubeUnitOfWork(SqlAlchemyUnitOfWork):
    """Wires the YouTube collaborators onto a single session for one operation.

    Implements `IYoutubeUnitOfWork`. Every repository here shares the unit of work's
    session, so they flush instead of committing and the whole operation commits or
    rolls back together.
    """

    # Declared as the interfaces, not the concrete classes: protocol attributes are
    # mutable and therefore invariant, so a narrower type would not satisfy them.
    contents: IYoutubeContentService
    monitored_channels: IYouTubeMonitoredChannelRepository
    channels: IYouTubeChannelRepository

    def __init__(
        self,
        logger: ILogger,
        session_factory: Callable[[], Session] = DefaultSessionFactory,
    ) -> None:
        super().__init__(session_factory=session_factory)
        self._logger = logger

    def __enter__(self) -> YoutubeUnitOfWork:
        super().__enter__()
        session = self.session
        self.contents = YoutubeContentService(
            repository=YoutubeContentRepository(session=session, logger=self._logger),
            logger=self._logger,
        )
        self.monitored_channels = YouTubeMonitoredChannelRepository(
            session=session, logger=self._logger
        )
        self.channels = YouTubeChannelRepository(session=session, logger=self._logger)
        return self
