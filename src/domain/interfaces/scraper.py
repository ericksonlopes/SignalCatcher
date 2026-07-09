from typing import Protocol

from src.domain.models.youtube_video_dto import YouTubeVideoDTO


class IYouTubeScraper(Protocol):
    def extract_channel_videos(self, channel_url: str) -> list[YouTubeVideoDTO]:
        """
        Extracts videos from a YouTube channel.
        
        Args:
            channel_url: The YouTube channel URL.
            
        Returns:
            A list of YouTubeVideoDTO objects.
        """
        ...

    def extract_video_info(self, video_url: str) -> YouTubeVideoDTO:
        """
        Extracts metadata from a single YouTube video.
        
        Args:
            video_url: The YouTube video URL.
            
        Returns:
            A YouTubeVideoDTO containing video metadata.
        """
        ...
