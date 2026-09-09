from src.core.logger.logger import logger
from src.modules.youtube.presentation.schedules.jobs.youtube_download_job import (
    download_videos_job,
)
from src.modules.youtube.presentation.schedules.jobs.youtube_extract_metadata_job import (
    extract_metadata_job,
)


def extract_and_download_job():
    """Runs metadata extraction to completion, then drains the download queue.

    Extraction and download used to be two independent scheduled jobs, which meant a
    download tick could fire while metadata was still being extracted and find nothing
    to do, leaving freshly extracted videos waiting for the next tick. Chaining them in
    a single job guarantees every video that just became downloadable is picked up in
    the same run.

    Both steps already swallow and log their own exceptions, so a failure inside
    extraction never prevents the download phase from running.
    """
    logger.info("Starting scheduled job: Extract Metadata + Download Videos")

    extract_metadata_job()

    logger.info("Metadata extraction phase done. Starting download phase.")
    download_videos_job()

    logger.info("Extract Metadata + Download Videos job finished.")
