from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.interfaces.youtube_monitored_channel_repository import IYouTubeMonitoredChannelRepository
from src.modules.youtube.domain.interfaces.channel_service import IChannelService
from src.modules.youtube.domain.entities.channel_entity import ChannelEntity


class ChannelService(IChannelService):
    def __init__(self, repository: IYouTubeMonitoredChannelRepository, logger: ILogger):
        self.repository = repository
        self.logger = logger

    def create_channel(self, channel_entity: ChannelEntity) -> ChannelEntity:
        existing_channel = self.repository.get_by_url(url=channel_entity.url)
        if existing_channel:
            self.logger.warning(f"Attempt to duplicate channel: {channel_entity.url}", context={"url": channel_entity.url})
            raise ValueError("A channel with this URL already exists.")

        new_channel = self.repository.create(channel_entity)

        self.logger.debug(f"New channel created successfully: {new_channel.name}", context={"channel_id": new_channel.id, "channel_name": new_channel.name})
        return new_channel
