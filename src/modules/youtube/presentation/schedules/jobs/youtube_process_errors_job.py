from src.core.config.settings import settings
from src.core.logger.logger import logger as global_logger
from src.modules.youtube.application.use_cases.jobs.process_errors_use_case import (
    ProcessErrorsUseCase,
)
from src.modules.youtube.application.use_cases.jobs.reprocess_video_use_case import (
    ReprocessVideoUseCase,
)
from src.modules.youtube.infrastructure.services.youtube_scraper import (
    YouTubeScraperService,
)
from src.modules.youtube.infrastructure.unit_of_work import YoutubeUnitOfWork


def process_errors_job():
    global_logger.info("Starting error retry process...")

    scraper = YouTubeScraperService(logger=global_logger)
    use_case = ProcessErrorsUseCase(
        uow_factory=lambda: YoutubeUnitOfWork(logger=global_logger),
        scraper=scraper,
        output_path=settings.DOWNLOAD_YOUTUBE_PATH,
        logger=global_logger,
    )

    try:
        retried = use_case.execute()
        global_logger.info(f"Error retry process finished. {retried} videos retried.")
    except Exception as e:
        global_logger.error(f"Error retry job aborted: {e}")


def reprocess_single_video_job(external_id: str):
    global_logger.info(f"Starting individual reprocessing for video {external_id}...")

    scraper = YouTubeScraperService(logger=global_logger)
    use_case = ReprocessVideoUseCase(
        uow_factory=lambda: YoutubeUnitOfWork(logger=global_logger),
        scraper=scraper,
        output_path=settings.DOWNLOAD_YOUTUBE_PATH,
        logger=global_logger,
    )

    use_case.execute(external_id)


if __name__ == "__main__":
    process_errors_job()
