from src.application.use_cases.extract_metadata_use_case import ExtractMetadataUseCase
from src.infrastructure.loggers.logger import logger
from src.infrastructure.repositories.youtube_content_repository import (
    YoutubeContentRepository,
)
from src.infrastructure.services.youtube_scraper import YouTubeScraperService


def extract_metadata_job():
    """Job to run the metadata extraction script."""
    logger.info("Starting scheduled job: Extract Metadata")

    repo = YoutubeContentRepository(logger=logger)
    scraper = YouTubeScraperService(logger=logger)
    use_case = ExtractMetadataUseCase(
        youtube_content_repository=repo, youtube_scraper=scraper, logger=logger
    )

    try:
        while True:
            processed_something = use_case.execute()
            if not processed_something:
                break
        logger.info("Extract Metadata job finished successfully.")
    except Exception as e:
        logger.error(f"Error running Extract Metadata job: {e}")
