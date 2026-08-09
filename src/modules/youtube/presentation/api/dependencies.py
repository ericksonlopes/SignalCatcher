from fastapi import Depends

from src.core.logger.interfaces import ILogger
from src.modules.youtube.application.use_cases.channels_use_case import ChannelsUseCase
from src.core.logger.logger import logger as global_logger
from src.modules.youtube.infrastructure.repositories.youtube_monitored_channel_repository import YouTubeMonitoredChannelRepository
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


def get_channels_use_case(
    service: ChannelService = Depends(get_channel_service),
    repository: YouTubeMonitoredChannelRepository = Depends(get_youtube_monitored_channel_repository),
    logger: ILogger = Depends(get_logger)
) -> ChannelsUseCase:
    """
    Factory for the consolidated ChannelsUseCase.
    """
    from src.modules.youtube.infrastructure.services.youtube_scraper import YouTubeScraperService
    from src.modules.youtube.infrastructure.repositories.youtube_channel_repository import YouTubeChannelRepository
    
    scraper = YouTubeScraperService(logger=logger)
    yt_channel_repo = YouTubeChannelRepository(logger=logger)
    
    return ChannelsUseCase(
        channel_service=service, 
        repository=repository, 
        logger=logger, 
        scraper=scraper, 
        yt_channel_repo=yt_channel_repo
    )
