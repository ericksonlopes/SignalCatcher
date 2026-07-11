import time
from typing import Iterable, Any

from yt_dlp import YoutubeDL

from src.application.interfaces.ilogger import ILogger
from src.domain.interfaces.scraper import IYouTubeScraper
from src.domain.models.youtube_video_dto import YouTubeVideoDTO


class YouTubeScraperService(IYouTubeScraper):
    def __init__(self, logger: ILogger):
        self.logger = logger

    @staticmethod
    def _get_common_ydl_opts() -> dict:
        return {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'ignoreerrors': True,
        }

    @staticmethod
    def _parse_channel_entries(entries: Iterable[Any], default_channel: str = "") -> list[YouTubeVideoDTO]:
        videos = []
        for entry in entries:
            if not entry:
                continue

            video_id = entry.get('id')
            if not video_id:
                continue

            videos.append(
                YouTubeVideoDTO(
                    id=video_id,
                    title=entry.get('title'),
                    url=entry.get('url') or f"https://www.youtube.com/watch?v={video_id}",
                    channel=entry.get('channel') or entry.get('uploader') or default_channel
                )
            )
        return videos

    def _run_with_retry(self, func, retries=3, delay=2):
        for attempt in range(retries):
            try:
                return func()
            except Exception as e:
                if attempt == retries - 1:
                    raise
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay} seconds...",
                                    context={"attempt": attempt + 1, "error": str(e)})
                time.sleep(delay)
        return None

    def extract_channel_videos(self, channel_url: str) -> list[YouTubeVideoDTO]:
        """Extracts all videos from a YouTube channel with metadata.

        Returns a list of YouTubeVideoDTO objects.
        Uses extract_flat to avoid downloading any video content.
        """
        self.logger.debug(f"Starting channel video extraction for {channel_url}", context={"channel_url": channel_url})

        # Normalize: ensure URL ends with /videos for complete listing
        normalized_url = channel_url.rstrip("/")
        if not normalized_url.endswith("/videos"):
            normalized_url = f"{normalized_url}/videos"

        def _extract():
            ydl_opts = self._get_common_ydl_opts()
            ydl_opts.update({"extract_flat": "in_playlist", "ignore_unavailable": True})

            with YoutubeDL(ydl_opts) as ydl:
                channel_info = ydl.extract_info(normalized_url, download=False)
                if not channel_info or "entries" not in channel_info:
                    extracted_channel_name = channel_info.get("channel", "") if channel_info else ""
                    return [], extracted_channel_name

                extracted_channel_name = channel_info.get("channel") or channel_info.get("uploader") or ""
                extracted_videos = self._parse_channel_entries(channel_info["entries"], default_channel=extracted_channel_name)
                return extracted_videos, extracted_channel_name

        try:
            videos, channel_name = self._run_with_retry(_extract)

            self.logger.debug(
                f"Channel videos extracted successfully. "
                f"Channel: {channel_name} | Count: {len(videos)}",
                context={"channel_name": channel_name, "video_count": len(videos)}
            )
            return videos
        except Exception as e:
            self.logger.error(f"Channel extraction failed for {channel_url}",
                              context={"channel_url": channel_url, "error": str(e)})
            raise

    def extract_video_info(self, video_url: str) -> YouTubeVideoDTO:
        """Extracts metadata from a single YouTube video.

        Returns a YouTubeVideoDTO containing video metadata.
        Uses extract_flat to avoid downloading any video content.
        """
        self.logger.debug(f"Starting video extraction for {video_url}", context={"video_url": video_url})

        def _extract():
            ydl_opts = self._get_common_ydl_opts()
            
            with YoutubeDL(ydl_opts) as ydl:
                video_info = ydl.extract_info(video_url, download=False)
                if not video_info:
                    raise Exception("Failed to extract video information.")

                return YouTubeVideoDTO(
                    id=video_info.get("id"),
                    title=video_info.get("title"),
                    channel=video_info.get("channel") or video_info.get("uploader") or "YouTube",
                    url=video_url,
                )

        try:
            return self._run_with_retry(_extract)
        except Exception as e:
            self.logger.error(f"Video extraction failed for {video_url}",
                              context={"video_url": video_url, "error": str(e)})
            raise

    def extract_playlist_videos(self, playlist_url: str) -> list[YouTubeVideoDTO]:
        """Extracts all videos from a YouTube playlist.

        Returns a list of YouTubeVideoDTO objects.
        Uses extract_flat to avoid downloading any video content.
        """
        self.logger.debug(f"Starting playlist video extraction for {playlist_url}", context={"playlist_url": playlist_url})

        def _extract():
            ydl_opts = self._get_common_ydl_opts()
            ydl_opts.update({"extract_flat": "in_playlist", "ignore_unavailable": True})

            with YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(playlist_url, download=False)
                if not playlist_info or "entries" not in playlist_info:
                    return []

                playlist_channel = playlist_info.get("channel") or playlist_info.get("uploader") or ""
                return self._parse_channel_entries(playlist_info["entries"], default_channel=playlist_channel)

        try:
            videos = self._run_with_retry(_extract)

            self.logger.debug(
                f"Playlist videos extracted successfully. "
                f"Count: {len(videos)}",
                context={"playlist_url": playlist_url, "video_count": len(videos)}
            )
            return videos
        except Exception as e:
            self.logger.error(f"Playlist extraction failed for {playlist_url}",
                              context={"playlist_url": playlist_url, "error": str(e)})
            raise
