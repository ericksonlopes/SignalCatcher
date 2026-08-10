from fastapi import Depends

from src.core.config.settings import settings
from src.core.logger.interfaces import ILogger
from src.core.logger.logger import logger as global_logger
from src.modules.youtube.infrastructure.repositories.youtube_content_repository import (
    YoutubeContentRepository,
)
from src.modules.youtube.infrastructure.repositories.youtube_monitored_channel_repository import (
    YouTubeMonitoredChannelRepository,
)
from src.modules.youtube.infrastructure.services.channel_service import ChannelService


def get_logger() -> ILogger:
    return global_logger


def get_youtube_monitored_channel_repository(logger: ILogger = Depends(get_logger)) -> YouTubeMonitoredChannelRepository:
    return YouTubeMonitoredChannelRepository(logger=logger)


def get_channel_service(
    repository: YouTubeMonitoredChannelRepository = Depends(get_youtube_monitored_channel_repository),
    logger: ILogger = Depends(get_logger)
) -> ChannelService:
    return ChannelService(repository=repository, logger=logger)


def get_channel_commands(
    service: ChannelService = Depends(get_channel_service),
    repository: YouTubeMonitoredChannelRepository = Depends(
        get_youtube_monitored_channel_repository
    ),
    logger: ILogger = Depends(get_logger),
) -> "ChannelCommands":
    from src.modules.youtube.infrastructure.services.youtube_scraper import YouTubeScraperService
    from src.modules.youtube.infrastructure.repositories.youtube_channel_repository import YouTubeChannelRepository
    from src.modules.youtube.application.use_cases.channels.channel_commands import (
        ChannelCommands,
    )

    scraper = YouTubeScraperService(logger=logger)
    yt_channel_repo = YouTubeChannelRepository(logger=logger)

    return ChannelCommands(
        channel_service=service,
        repository=repository,
        logger=logger,
        scraper=scraper,
        yt_channel_repo=yt_channel_repo,
    )


def get_channel_queries(
    repository: YouTubeMonitoredChannelRepository = Depends(
        get_youtube_monitored_channel_repository
    ),
    logger: ILogger = Depends(get_logger),
) -> "ChannelQueries":
    from src.modules.youtube.infrastructure.repositories.youtube_channel_repository import (
        YouTubeChannelRepository,
    )
    from src.modules.youtube.application.use_cases.channels.channel_queries import (
        ChannelQueries,
    )

    yt_channel_repo = YouTubeChannelRepository(logger=logger)

    return ChannelQueries(
        repository=repository, logger=logger, yt_channel_repo=yt_channel_repo
    )


def get_youtube_content_repository(
    logger: ILogger = Depends(get_logger),
) -> YoutubeContentRepository:
    return YoutubeContentRepository(logger=logger)


def get_youtube_content_service(
    repository: YoutubeContentRepository = Depends(get_youtube_content_repository),
    logger: ILogger = Depends(get_logger),
):
    from src.modules.youtube.infrastructure.services.youtube_content_service import (
        YoutubeContentService,
    )

    return YoutubeContentService(repository=repository, logger=logger)


def get_content_commands(
    service=Depends(get_youtube_content_service),
    logger: ILogger = Depends(get_logger),
) -> "ContentCommands":
    from src.modules.youtube.application.use_cases.content.content_commands import (
        ContentCommands,
    )

    return ContentCommands(
        service=service, output_path=settings.DOWNLOAD_YOUTUBE_PATH, logger=logger
    )


def get_content_queries(
    service=Depends(get_youtube_content_service),
) -> "ContentQueries":
    from src.modules.youtube.application.use_cases.content.content_queries import (
        ContentQueries,
    )

    return ContentQueries(service=service)


def get_add_content_from_link_use_case(
    service=Depends(get_youtube_content_service),
    logger: ILogger = Depends(get_logger),
):
    from src.modules.youtube.application.use_cases.content.add_content_from_link_use_case import (
        AddContentFromLinkUseCase,
    )
    from src.modules.youtube.infrastructure.services.youtube_scraper import (
        YouTubeScraperService,
    )
    from src.core.notifications.voice_monkey_notification import (
        VoiceMonkeyNotification,
    )

    scraper = YouTubeScraperService(logger=logger)
    notification = VoiceMonkeyNotification(
        api_token=settings.VOICE_MONKEY_API_TOKEN,
        monkey_id=settings.VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID,
        logger=logger,
    )
    return AddContentFromLinkUseCase(
        youtube_content_service=service,
        youtube_scraper=scraper,
        notification=notification,
        logger=logger,
    )


def get_add_content_from_playlist_use_case(
    service=Depends(get_youtube_content_service),
    logger: ILogger = Depends(get_logger),
):
    from src.modules.youtube.application.use_cases.content.add_content_from_playlist_use_case import (
        AddContentFromPlaylistUseCase,
    )
    from src.modules.youtube.infrastructure.services.youtube_scraper import (
        YouTubeScraperService,
    )

    scraper = YouTubeScraperService(logger=logger)
    return AddContentFromPlaylistUseCase(
        youtube_content_service=service, youtube_scraper=scraper, logger=logger
    )
