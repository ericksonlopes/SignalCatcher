from src.core.config.settings import settings
from src.core.logger.logger import logger as global_logger
from src.modules.youtube.application.use_cases.jobs.download_video_use_case import (
    DownloadVideoUseCase,
)
from src.modules.youtube.infrastructure.services.youtube_scraper import (
    YouTubeScraperService,
)
from src.modules.youtube.infrastructure.unit_of_work import YoutubeUnitOfWork


def download_videos_job():
    global_logger.info("Starting video download process...")

    scraper = YouTubeScraperService(logger=global_logger)
    use_case = DownloadVideoUseCase(
        # A factory, not an instance: the use case opens a fresh transaction per
        # phase instead of keeping one open across the whole download.
        uow_factory=lambda: YoutubeUnitOfWork(logger=global_logger),
        scraper=scraper,
        output_path=settings.DOWNLOAD_YOUTUBE_PATH,
        logger=global_logger,
    )

    try:
        # execute() processes one pending video per call and returns False when the
        # queue is empty, so drain it by counting how many were handled.
        processed = 0
        while use_case.execute():
            processed += 1
        global_logger.info(
            f"No more videos pending download. Finishing. Processed {processed}."
        )
    except Exception as e:
        global_logger.error(f"Download job aborted: {e}")


if __name__ == "__main__":
    download_videos_job()
