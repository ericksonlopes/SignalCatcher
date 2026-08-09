from src.modules.youtube.application.use_cases.extract_metadata_use_case import ExtractMetadataUseCase
from src.core.logger.logger import logger
from src.modules.youtube.infrastructure.repositories.youtube_channel_repository import YouTubeChannelRepository
from src.modules.youtube.infrastructure.repositories.youtube_content_repository import (
    YoutubeContentRepository,
)
from src.modules.youtube.infrastructure.services.youtube_scraper import YouTubeScraperService


def extract_metadata_job():
    """Job to run the metadata extraction script."""
    logger.info("Starting scheduled job: Extract Metadata")

    repo = YoutubeContentRepository(logger=logger)
    scraper = YouTubeScraperService(logger=logger)
    channel_repo = YouTubeChannelRepository(logger=logger)
    use_case = ExtractMetadataUseCase(
        youtube_content_repository=repo, youtube_scraper=scraper, youtube_channel_repository=channel_repo, logger=logger
    )

    try:
        from src.modules.youtube.domain.enums.content_step import ContentStep
        
        # Self-healing: Reset any items stuck in EXTRACTING_METADATA from a previous crashed run
        stuck_count = repo.reset_stuck_steps(
            stuck_step=ContentStep.EXTRACTING_METADATA, 
            pending_step=ContentStep.PENDING_METADATA_EXTRACTION
        )
        if stuck_count > 0:
            logger.info(f"Self-healing: Reverted {stuck_count} stuck items from EXTRACTING_METADATA to PENDING_METADATA_EXTRACTION.")

        while True:
            processed_something = use_case.execute()
            if not processed_something:
                break
        logger.info("Extract Metadata job finished successfully.")
    except Exception as e:
        logger.error(f"Error running Extract Metadata job: {e}")
