from collections.abc import Iterator

from fastapi import Depends

from src.core.config.settings import settings
from src.core.logger.interfaces import ILogger
from src.core.logger.logger import logger as global_logger
from src.core.notifications.voice_monkey_notification import VoiceMonkeyNotification
from src.modules.youtube.application.use_cases.channels.channel_commands import (
    ChannelCommands,
)
from src.modules.youtube.application.use_cases.channels.channel_queries import (
    ChannelQueries,
)
from src.modules.youtube.application.use_cases.content.add_content_from_link_use_case import (
    AddContentFromLinkUseCase,
)
from src.modules.youtube.application.use_cases.content.add_content_from_playlist_use_case import (
    AddContentFromPlaylistUseCase,
)
from src.modules.youtube.application.use_cases.content.content_commands import (
    ContentCommands,
)
from src.modules.youtube.application.use_cases.content.content_queries import (
    ContentQueries,
)
from src.modules.youtube.domain.interfaces.repositories.youtube_channel_repository import (
    IYouTubeChannelRepository,
)
from src.modules.youtube.domain.interfaces.repositories.youtube_monitored_channel_repository import (
    IYouTubeMonitoredChannelRepository,
)
from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)
from src.modules.youtube.infrastructure.services.channel_service import ChannelService
from src.modules.youtube.infrastructure.services.youtube_scraper import (
    YouTubeScraperService,
)
from src.modules.youtube.infrastructure.unit_of_work import YoutubeUnitOfWork


def get_logger() -> ILogger:
    return global_logger


def get_unit_of_work(
    logger: ILogger = Depends(get_logger),
) -> Iterator[YoutubeUnitOfWork]:
    """Provides one transaction per request.

    FastAPI caches dependencies within a request, so every collaborator below shares
    this unit of work and therefore a single transaction. The commit sits after the
    yield, which is only reached when the endpoint returned without raising: a failed
    request leaves the block through `__exit__`, which rolls back.
    """
    with YoutubeUnitOfWork(logger=logger) as uow:
        yield uow
        uow.commit()


def get_youtube_monitored_channel_repository(
    uow: YoutubeUnitOfWork = Depends(get_unit_of_work),
) -> IYouTubeMonitoredChannelRepository:
    return uow.monitored_channels


def get_youtube_channel_repository(
    uow: YoutubeUnitOfWork = Depends(get_unit_of_work),
) -> IYouTubeChannelRepository:
    return uow.channels


def get_youtube_content_service(
    uow: YoutubeUnitOfWork = Depends(get_unit_of_work),
) -> IYoutubeContentService:
    return uow.contents


def get_channel_service(
    repository: IYouTubeMonitoredChannelRepository = Depends(
        get_youtube_monitored_channel_repository
    ),
    logger: ILogger = Depends(get_logger),
) -> ChannelService:
    return ChannelService(repository=repository, logger=logger)


def get_channel_commands(
    service: ChannelService = Depends(get_channel_service),
    repository: IYouTubeMonitoredChannelRepository = Depends(
        get_youtube_monitored_channel_repository
    ),
    yt_channel_repo: IYouTubeChannelRepository = Depends(
        get_youtube_channel_repository
    ),
    logger: ILogger = Depends(get_logger),
) -> ChannelCommands:
    return ChannelCommands(
        channel_service=service,
        repository=repository,
        logger=logger,
        scraper=YouTubeScraperService(logger=logger),
        yt_channel_repo=yt_channel_repo,
    )


def get_channel_queries(
    repository: IYouTubeMonitoredChannelRepository = Depends(
        get_youtube_monitored_channel_repository
    ),
    yt_channel_repo: IYouTubeChannelRepository = Depends(
        get_youtube_channel_repository
    ),
    logger: ILogger = Depends(get_logger),
) -> ChannelQueries:
    return ChannelQueries(
        repository=repository, logger=logger, yt_channel_repo=yt_channel_repo
    )


def get_content_commands(
    service: IYoutubeContentService = Depends(get_youtube_content_service),
    logger: ILogger = Depends(get_logger),
) -> ContentCommands:
    return ContentCommands(
        service=service, output_path=settings.DOWNLOAD_YOUTUBE_PATH, logger=logger
    )


def get_content_queries(
    service: IYoutubeContentService = Depends(get_youtube_content_service),
) -> ContentQueries:
    return ContentQueries(service=service)


def get_add_content_from_link_use_case(
    service: IYoutubeContentService = Depends(get_youtube_content_service),
    logger: ILogger = Depends(get_logger),
) -> AddContentFromLinkUseCase:
    notification = VoiceMonkeyNotification(
        api_token=settings.VOICE_MONKEY_API_TOKEN,
        monkey_id=settings.VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID,
        logger=logger,
    )
    return AddContentFromLinkUseCase(
        youtube_content_service=service,
        youtube_scraper=YouTubeScraperService(logger=logger),
        notification=notification,
        logger=logger,
    )


def get_add_content_from_playlist_use_case(
    service: IYoutubeContentService = Depends(get_youtube_content_service),
    logger: ILogger = Depends(get_logger),
) -> AddContentFromPlaylistUseCase:
    return AddContentFromPlaylistUseCase(
        youtube_content_service=service,
        youtube_scraper=YouTubeScraperService(logger=logger),
        logger=logger,
    )
