from typing import Protocol


class IYouTubeChannelRepository(Protocol):
    def upsert_channel(self, channel_info: dict) -> None:
        """Inserts or updates a YouTube channel metadata record."""
        ...

    def get_all(self) -> list:
        """Retrieves all saved YouTube channels."""
        ...
