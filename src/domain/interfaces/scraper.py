from typing import Protocol

from src.domain.models.youtube_channel_result_dto import YouTubeChannelResultDTO


class IYouTubeScraper(Protocol):
    def extract_channel_videos(self, channel_url: str) -> YouTubeChannelResultDTO:
        """
        Extracts videos from a YouTube channel.
        
        Args:
            channel_url: The YouTube channel URL.
            
        Returns:
            YouTubeChannelResultDTO containing channel and video information.
        """
        ...
