from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.youtube_content_repository import IYoutubeContentRepository
from src.domain.interfaces.scraper import IYouTubeScraper
from src.domain.models.enums.content_step import ContentStep
import datetime

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

            # Complete step
            content.step = ContentStep.COMPLETED
            self.youtube_content_repository.update(content)
            self.logger.info(f"Successfully extracted metadata for: {content.title}")

        except Exception as e:
            self.logger.error(f"Error extracting metadata for {content.title}: {e}")
            content.error_info = str(e)
            content.step = ContentStep.ERROR
            self.youtube_content_repository.update(content)

        return True
