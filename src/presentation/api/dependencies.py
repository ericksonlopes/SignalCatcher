from fastapi import Depends

from src.domain.interfaces.logger import ILogger
from src.application.use_cases.channels_use_case import ChannelsUseCase
from src.infrastructure.loggers.logger import logger as global_logger
from src.infrastructure.repositories.youtube_monitored_channel_repository import YouTubeMonitoredChannelRepository
from src.infrastructure.services.channel_service import ChannelService

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
    return ChannelsUseCase(channel_service=service, repository=repository, logger=logger)
