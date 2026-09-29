from typing import Protocol

from src.modules.youtube.domain.entities.channel_entity import ChannelEntity


class IYouTubeMonitoredChannelRepository(Protocol):
    def get_by_url(self, url: str) -> ChannelEntity | None:
        """Fetches a channel by its URL."""
        ...

    def get_by_id(self, channel_id: int) -> ChannelEntity | None:
        """Fetches a channel by its ID."""
        ...

    def create(self, channel_data: ChannelEntity) -> ChannelEntity:
        """Saves a new channel to the database."""
        ...

    def get_all_active(self) -> list[ChannelEntity]:
        """Fetches all active channels from the database."""
        ...

    def get_all(self) -> list[ChannelEntity]:
        """Fetches all channels from the database."""
        ...

    def update(self, channel_entity: ChannelEntity) -> ChannelEntity:
        """Updates an existing channel in the database."""
        ...
