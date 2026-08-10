from src.core.logger.interfaces import ILogger
from src.core.interfaces.notifications.notification import INotification
from src.modules.youtube.domain.interfaces.services.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.services.youtube_content_service import IYoutubeContentService
from src.modules.youtube.domain.entities.youtube_content_entity import YoutubeContentEntity


class AddContentFromLinkUseCase:
    def __init__(self, youtube_content_service: IYoutubeContentService, youtube_scraper: IYouTubeScraper, notification: INotification, logger: ILogger):
        self.youtube_content_service = youtube_content_service
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

        created_content = self.youtube_content_service.add_new_content(
            external_id=info.id,
            title=info.title or "Untitled",
            url=info.url,
            origin=info.channel
        )
        
        self.logger.info(
            f"Content created successfully (id={created_content.id}). Triggering VoiceMonkey notification...",
            context={"content_id": created_content.id, "external_id": info.id, "title": info.title}
        )
        self.notification.send()
        return created_content
