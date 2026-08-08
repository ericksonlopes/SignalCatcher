from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.scraper import IYouTubeScraper
from src.domain.interfaces.youtube_content_repository import IYoutubeContentRepository
from src.domain.models.enums.content_step import ContentStep
from src.domain.models.youtube_content_entity import YoutubeContentEntity

class AddContentFromPlaylistUseCase:
    def __init__(self, youtube_content_repository: IYoutubeContentRepository, youtube_scraper: IYouTubeScraper, logger: ILogger):
        self.youtube_content_repository = youtube_content_repository
        self.youtube_scraper = youtube_scraper
        self.logger = logger

    def execute(self, playlist_url: str, save_in_playlist_folder: bool = False) -> list[YoutubeContentEntity]:
        if not self._is_youtube_link(playlist_url):
            raise ValueError(f"URL '{playlist_url}' is not a valid YouTube link.")

        self.logger.info(f"Extracting YouTube playlist videos from {playlist_url}")
        videos, playlist_title = self.youtube_scraper.extract_playlist_videos(playlist_url)

        if not videos:
            self.logger.warning(f"No videos found in playlist or failed to extract: {playlist_url}")
            return []

        saved_contents = []
        for video in videos:
            if self.youtube_content_repository.exists_by_external_id(video.id):
                self.logger.info(f"Content with external_id {video.id} already exists. Skipping.")
                continue

            origin = video.channel or "Unknown Channel"
            if save_in_playlist_folder:
                origin = f"{origin}/{playlist_title}"

            content = YoutubeContentEntity(
                external_id=video.id,
                title=video.title or "Untitled",
                url=video.url,
                origin=origin,
                step=ContentStep.STARTED
            )
            saved_content = self.youtube_content_repository.create(content)

            saved_content.step = ContentStep.PENDING_METADATA_EXTRACTION
            self.youtube_content_repository.update(saved_content)

            saved_contents.append(saved_content)

        self.logger.info(f"Successfully added {len(saved_contents)} new videos from playlist.")
        return saved_contents

    def _is_youtube_link(self, url: str) -> bool:
        return "youtube.com" in url or "youtu.be" in url
