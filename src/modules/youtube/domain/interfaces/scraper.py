from typing import Protocol

from src.modules.youtube.domain.entities.youtube_video_dto import YouTubeVideoDTO


class IYouTubeScraper(Protocol):
    def extract_metadata(self, video_url: str) -> dict:
        """
        Extracts detailed metadata from a single YouTube video.
        
        Args:
            video_url: The YouTube video URL.
            
        Returns:
            A dict containing detailed metadata.
        """
        ...
    def extract_channel_videos(self, channel_url: str) -> list[YouTubeVideoDTO]:
        """
        Extracts videos from a YouTube channel.
        
        Args:
            channel_url: The YouTube channel URL.
            
        Returns:
            A list of YouTubeVideoDTO objects.
        """
        ...

    def extract_channel_info(self, channel_url: str) -> dict:
        """
        Extracts metadata from a YouTube channel.
        
        Args:
            channel_url: The YouTube channel URL.
            
        Returns:
            A dict containing channel metadata.
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

    def extract_playlist_videos(self, playlist_url: str) -> tuple[list[YouTubeVideoDTO], str]:
        """
        Extracts videos from a YouTube playlist.
        
        Args:
            playlist_url: The YouTube playlist URL.
            
        Returns:
            A tuple containing a list of YouTubeVideoDTO objects and the playlist title.
        """
        ...
