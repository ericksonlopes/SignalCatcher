from src.core.logger.logger import logger
from src.modules.youtube.application.use_cases.jobs.extract_metadata_use_case import (
    ExtractMetadataUseCase,
)
from src.modules.youtube.infrastructure.services.youtube_scraper import (
    YouTubeScraperService,
)
from src.modules.youtube.infrastructure.unit_of_work import YoutubeUnitOfWork


def extract_metadata_job():
    """Job to run the metadata extraction script."""
    logger.info("Starting scheduled job: Extract Metadata")

    scraper = YouTubeScraperService(logger=logger)
    use_case = ExtractMetadataUseCase(
        # A factory, not an instance: the use case opens a fresh transaction per
        # phase instead of holding one open across the whole batch.
        uow_factory=lambda: YoutubeUnitOfWork(logger=logger),
        youtube_scraper=scraper,
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
