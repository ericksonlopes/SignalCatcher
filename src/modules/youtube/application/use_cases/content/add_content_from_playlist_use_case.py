from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.entities.youtube_content_entity import (
    YoutubeContentEntity,
)
from src.modules.youtube.domain.interfaces.services.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)


class AddContentFromPlaylistUseCase:
    def __init__(
        self,
        youtube_content_service: IYoutubeContentService,
        youtube_scraper: IYouTubeScraper,
        logger: ILogger,
    ):
        self.youtube_content_service = youtube_content_service
        self.youtube_scraper = youtube_scraper
        self.logger = logger

    def execute(
        self, playlist_url: str, save_in_playlist_folder: bool = False
    ) -> list[YoutubeContentEntity]:
        if not self._is_youtube_link(playlist_url):
            raise ValueError(f"URL '{playlist_url}' is not a valid YouTube link.")

        self.logger.info(f"Extracting YouTube playlist videos from {playlist_url}")
        videos, playlist_title = self.youtube_scraper.extract_playlist_videos(
            playlist_url
        )

        if not videos:
            self.logger.warning(
                f"No videos found in playlist or failed to extract: {playlist_url}"
            )
            return []

        saved_contents = []
        for video in videos:
            if self.youtube_content_service.exists_by_external_id(video.id):
                self.logger.info(
                    f"Content with external_id {video.id} already exists. Skipping."
                )
                continue

            origin = video.channel or "Unknown Channel"
            if save_in_playlist_folder:
                origin = f"{origin}/{playlist_title}"

            saved_content = self.youtube_content_service.add_new_content(
                external_id=video.id,
                title=video.title or "Untitled",
                url=video.url,
                origin=origin,
            )

            saved_contents.append(saved_content)

        self.logger.info(
            f"Successfully added {len(saved_contents)} new videos from playlist."
        )
        return saved_contents

    def _is_youtube_link(self, url: str) -> bool:
        return "youtube.com" in url or "youtu.be" in url
