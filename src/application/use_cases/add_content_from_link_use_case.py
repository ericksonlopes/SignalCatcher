from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.content_repository import IContentRepository
from src.domain.interfaces.scraper import IYouTubeScraper
from src.domain.models.content_entity import ContentEntity
from src.domain.models.enums.content_status import ContentStatus
from src.domain.models.enums.source_platform import SourcePlatform


class AddContentFromLinkUseCase:
    def __init__(self, content_repository: IContentRepository, youtube_scraper: IYouTubeScraper, logger: ILogger):
        self.content_repository = content_repository
        self.youtube_scraper = youtube_scraper
        self.logger = logger

    def execute(self, url: str) -> ContentEntity:
        if self._is_youtube_link(url):
            return self._process_youtube_link(url)

        raise ValueError(f"URL '{url}' is not supported yet.")

    def _is_youtube_link(self, url: str) -> bool:
        return "youtube.com" in url or "youtu.be" in url

    def _process_youtube_link(self, url: str) -> ContentEntity:
        self.logger.info(f"Extracting YouTube video info from {url}")
        info = self.youtube_scraper.extract_video_info(url)

        if not info or not info.id:
            raise ValueError(f"Failed to extract info from YouTube URL: {url}")

        if self.content_repository.exists_by_external_id(info.id):
            self.logger.warning(f"Content with external_id {info.id} already exists.")
            raise ValueError("Content already exists.")

        content = ContentEntity(
            external_id=info.id,
            title=info.title or "Untitled",
            url=info.url,
            source_platform=SourcePlatform.YOUTUBE,
            origin=info.channel,
            status=ContentStatus.PENDING_DOWNLOAD
        )

        return self.content_repository.create(content)
