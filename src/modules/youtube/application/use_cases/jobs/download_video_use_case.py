from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.error_classifier import (
    classify_youtube_error,
    is_bot_block,
)
from src.modules.youtube.domain.interfaces.services.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)


class DownloadVideoUseCase:
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

    def execute(self) -> bool:
        """Downloads one pending video.

        Returns True if a video was processed, False if no pending videos remain.
        Raises Exception if YouTube bot detection is triggered.
        """
        content = self.youtube_content_service.get_first_by_step(
            ContentStep.PENDING_DOWNLOAD
        )

        if not content:
            return False

        self.logger.info(f"Processing download: {content.title} ({content.url})")

        # Transition to DOWNLOADING
        content.step = ContentStep.DOWNLOADING
        self.youtube_content_service.update_content(content)

        try:
            final_file_path = self.scraper.download_video(
                url=content.url,
                content_id=content.external_id,
                origin=content.origin,
                output_path=self.output_path,
            )
            
            import os
            from src.core.utils.file_utils import format_storage_path
            
            # Extract just the filename from the downloaded path
            filename = os.path.basename(final_file_path)
            
            # Create the storage path format (/youtube/canal/arquivo.ext)
            origin = content.origin or ""
            storage_path = format_storage_path(origin, filename)
            
            content.file_path = storage_path

            # Transition DOWNLOADED -> COMPLETED
            content.step = ContentStep.DOWNLOADED
            self.youtube_content_service.update_content(content)

            content.step = ContentStep.COMPLETED
            self.youtube_content_service.update_content(content)

            self.logger.info(f"Successfully downloaded: {content.title} to {storage_path}")

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error downloading {content.title}: {error_msg}")

            content.error_info = error_msg
            content.step = classify_youtube_error(error_msg)
            self.youtube_content_service.update_content(content)

            if is_bot_block(error_msg):
                self.logger.critical(
                    "YouTube bot block detected! Aborting download job."
                )
                raise

        return True
