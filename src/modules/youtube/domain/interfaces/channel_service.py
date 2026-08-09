from typing import Protocol

from src.modules.youtube.domain.entities.channel_entity import ChannelEntity


class IChannelService(Protocol):
    def create_channel(self, channel_entity: ChannelEntity) -> ChannelEntity:
        """Creates and persists a channel, validating necessary business rules in the infrastructure."""
        ...
