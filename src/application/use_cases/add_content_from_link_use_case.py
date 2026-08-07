from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.youtube_content_repository import IYoutubeContentRepository
from src.domain.interfaces.scraper import IYouTubeScraper
from src.domain.interfaces.notification import INotification
from src.domain.models.youtube_content_entity import YoutubeContentEntity
from src.domain.models.enums.content_step import ContentStep
from src.domain.models.enums.source_platform import SourcePlatform


class AddContentFromLinkUseCase:
    def __init__(self, youtube_content_repository: IYoutubeContentRepository, youtube_scraper: IYouTubeScraper, notification: INotification, logger: ILogger):
        self.youtube_content_repository = youtube_content_repository
        self.youtube_scraper = youtube_scraper
        self.notification = notification
        self.logger = logger

    def execute(self, url: str) -> YoutubeContentEntity:
        if self._is_youtube_link(url):
            return self._process_youtube_link(url)

        raise ValueError(f"URL '{url}' is not supported yet.")

    def _is_youtube_link(self, url: str) -> bool:
        return "youtube.com" in url or "youtu.be" in url

    def _process_youtube_link(self, url: str) -> YoutubeContentEntity:
        self.logger.info(f"Extracting YouTube video info from {url}")
        info = self.youtube_scraper.extract_video_info(url)

        if not info or not info.id:
            raise ValueError(f"Failed to extract info from YouTube URL: {url}")

        if self.youtube_content_repository.exists_by_external_id(info.id):
            self.logger.warning(f"Content with external_id {info.id} already exists.")
            raise ValueError("Content already exists.")

        content = YoutubeContentEntity(
            external_id=info.id,
            title=info.title or "Untitled",
            url=info.url,
            source_platform=SourcePlatform.YOUTUBE,
            origin=info.channel,
            step=ContentStep.PENDING_DOWNLOAD
        )

        created_content = self.youtube_content_repository.create(content)
        self.logger.info(
            f"Content created successfully (id={created_content.id}). Triggering VoiceMonkey notification...",
            context={"content_id": created_content.id, "external_id": info.id, "title": info.title}
        )
        self.notification.send()
        return created_content
