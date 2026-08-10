from src.core.logger.logger import logger
from src.modules.youtube.application.use_cases.jobs.extract_metadata_use_case import (
    ExtractMetadataUseCase,
)
from src.modules.youtube.infrastructure.repositories.youtube_channel_repository import (
    YouTubeChannelRepository,
)
from src.modules.youtube.infrastructure.repositories.youtube_content_repository import (
    YoutubeContentRepository,
)
from src.modules.youtube.infrastructure.services.youtube_content_service import (
    YoutubeContentService,
)
from src.modules.youtube.infrastructure.services.youtube_scraper import (
    YouTubeScraperService,
)


def extract_metadata_job():
    """Job to run the metadata extraction script."""
    logger.info("Starting scheduled job: Extract Metadata")

    repo = YoutubeContentRepository(logger=logger)
    service = YoutubeContentService(repository=repo, logger=logger)
    scraper = YouTubeScraperService(logger=logger)
    channel_repo = YouTubeChannelRepository(logger=logger)
    use_case = ExtractMetadataUseCase(
        youtube_content_service=service,
        youtube_scraper=scraper,
        youtube_channel_repository=channel_repo,
        logger=logger,
    )

    try:
        # Self-healing: Reset stuck items
        stuck_count = use_case.reset_stuck_items()
        if stuck_count > 0:
            logger.info(
                f"Self-healing: Reverted {stuck_count} stuck items "
                f"from EXTRACTING_METADATA to PENDING_METADATA_EXTRACTION."
            )

        while True:
            processed_something = use_case.execute()
            if not processed_something:
                break
        logger.info("Extract Metadata job finished successfully.")
    except Exception as e:
        logger.error(f"Error running Extract Metadata job: {e}")
