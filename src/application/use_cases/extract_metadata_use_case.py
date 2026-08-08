import datetime

from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.scraper import IYouTubeScraper
from src.domain.interfaces.youtube_content_repository import IYoutubeContentRepository
from src.domain.models.enums.content_step import ContentStep


class ExtractMetadataUseCase:
    def __init__(self, youtube_content_repository: IYoutubeContentRepository, youtube_scraper: IYouTubeScraper, logger: ILogger):
        self.youtube_content_repository = youtube_content_repository
        self.youtube_scraper = youtube_scraper
        self.logger = logger

    def execute(self) -> bool:
        """
        Executes one pending metadata extraction.
        Returns True if a content was processed, False if there are no pending contents.
        """
        content = self.youtube_content_repository.get_first_by_step(ContentStep.PENDING_METADATA_EXTRACTION)

        if not content:
            return False

        self.logger.info(f"Extracting metadata for content: {content.title} ({content.url})")

        # Transition to EXTRACTING_METADATA
        content.step = ContentStep.EXTRACTING_METADATA
        self.youtube_content_repository.update(content)

        try:
            # Extract metadata using the scraper
            metadata_dict = self.youtube_scraper.extract_metadata(content.url)

            content.raw_metadata = metadata_dict
            content.thumbnail = metadata_dict.get('thumbnail')
            
            duration_seconds = metadata_dict.get('duration')
            if duration_seconds:
                content.duration = str(datetime.timedelta(seconds=int(duration_seconds)))
            
            content.categories = metadata_dict.get('categories')
            content.tags = metadata_dict.get('tags')

            timestamp = metadata_dict.get('timestamp')
            if timestamp:
                content.published_at = datetime.datetime.fromtimestamp(int(timestamp), tz=datetime.timezone.utc)

            # Complete step
            content.step = ContentStep.METADATA_EXTRACTED
            self.youtube_content_repository.update(content)

            content.step = ContentStep.PENDING_DOWNLOAD
            self.youtube_content_repository.update(content)
            self.logger.info(f"Successfully extracted metadata for: {content.title}")

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error extracting metadata for {content.title}: {error_msg}")
            
            content.error_info = error_msg
            if "this video has been removed" in error_msg.lower():
                content.step = ContentStep.VIDEO_REMOVED
            else:
                content.step = ContentStep.ERROR
                
            self.youtube_content_repository.update(content)
            
            # If YouTube blocked our IP, we must abort the entire job loop to avoid hammering them.
            if "sign in to confirm you’re not a bot" in error_msg.lower() or "sign in to confirm" in error_msg.lower():
                self.logger.critical("YouTube bot block detected! Pausing scheduler job.")
                raise e

        return True
