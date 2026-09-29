from src.core.logger.logger import logger
from src.modules.youtube.presentation.schedules.jobs.youtube_download_job import (
    download_videos_job,
)
from src.modules.youtube.presentation.schedules.jobs.youtube_extract_metadata_job import (
    extract_metadata_job,
)


def extract_and_download_job():
    """Drain metadata then downloads; aborted phases reach worker telemetry."""
    logger.info("Starting scheduled job: Extract Metadata + Download Videos")

    extract_metadata_job()

    logger.info("Metadata extraction phase done. Starting download phase.")
    download_videos_job()

    logger.info("Extract Metadata + Download Videos job finished.")
