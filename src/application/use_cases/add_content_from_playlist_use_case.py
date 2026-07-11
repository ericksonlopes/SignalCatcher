from src.application.interfaces.ilogger import ILogger
from src.domain.interfaces.content_repository import IContentRepository
from src.domain.interfaces.scraper import IYouTubeScraper
from src.domain.models.content_entity import ContentEntity
from src.domain.models.enums.content_status import ContentStatus
from src.domain.models.enums.source_platform import SourcePlatform


class AddContentFromPlaylistUseCase:
    def __init__(self, content_repository: IContentRepository, youtube_scraper: IYouTubeScraper, logger: ILogger):
        self.content_repository = content_repository
        self.youtube_scraper = youtube_scraper
        self.logger = logger

    def execute(self, playlist_url: str, origin: str) -> list[ContentEntity]:
        if not self._is_youtube_link(playlist_url, origin):
            raise ValueError(f"Origin '{origin}' or URL '{playlist_url}' is not supported yet.")

        self.logger.info(f"Extracting YouTube playlist videos from {playlist_url}")
        videos = self.youtube_scraper.extract_playlist_videos(playlist_url)

        if not videos:
            self.logger.warning(f"No videos found in playlist or failed to extract: {playlist_url}")
            return []

        saved_contents = []
        for video in videos:
            if self.content_repository.exists_by_external_id(video.id):
                self.logger.info(f"Content with external_id {video.id} already exists. Skipping.")
                continue

            content = ContentEntity(
                external_id=video.id,
                title=video.title or "Untitled",
                url=video.url,
                source_platform=SourcePlatform.YOUTUBE,
                origin=video.channel or origin,
                status=ContentStatus.PENDING_DOWNLOAD
            )
            saved_content = self.content_repository.create(content)
            saved_contents.append(saved_content)

        self.logger.info(f"Successfully added {len(saved_contents)} new videos from playlist.")
        return saved_contents

    def _is_youtube_link(self, url: str, origin: str) -> bool:
        return origin.lower() == "youtube" or "youtube.com" in url or "youtu.be" in url
