from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.error_classifier import classify_youtube_error, is_bot_block
from src.modules.youtube.domain.interfaces.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.youtube_content_service import IYoutubeContentService


class ProcessErrorsUseCase:
    def __init__(
        self,
        youtube_content_service: IYoutubeContentService,
        scraper: IYouTubeScraper,
        output_path: str,
        logger: ILogger,
    ):
        self.youtube_content_service = youtube_content_service
        self.scraper = scraper
        self.output_path = output_path
        self.logger = logger

    def execute(self) -> int:
        """Retries downloading all videos currently in ERROR step.

        Returns the number of videos attempted.
        Raises Exception if YouTube bot detection is triggered.
        """
        retried_count = 0
        tried_ids: set[str] = set()

        while True:
            content = self.youtube_content_service.get_first_by_step(ContentStep.ERROR)
            if not content or content.external_id in tried_ids:
                break

            tried_ids.add(content.external_id)
            self.logger.info(f"Retrying content: {content.title} ({content.url})")
            if content.error_info:
                self.logger.warning(f"Previous Error: {content.error_info}")

            content.step = ContentStep.DOWNLOADING
            self.youtube_content_service.update_content(content)
            retried_count += 1

            try:
                self.scraper.download_video(
                    url=content.url,
                    content_id=content.external_id,
                    origin=content.origin,
                    output_path=self.output_path,
                )

                # On successful retry, reset to PENDING_METADATA_EXTRACTION
                content.step = ContentStep.PENDING_METADATA_EXTRACTION
                content.error_info = None
                self.youtube_content_service.update_content(content)

                self.logger.info(f"Successfully downloaded on retry: {content.title}")

            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"Error downloading again {content.title}: {error_msg}")

                content.error_info = error_msg
                content.step = classify_youtube_error(error_msg)
                self.youtube_content_service.update_content(content)

                if is_bot_block(error_msg):
                    self.logger.critical("YouTube bot block detected! Aborting error retry.")
                    raise

        return retried_count
