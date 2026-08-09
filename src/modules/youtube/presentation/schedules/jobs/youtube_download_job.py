from src.core.config.settings import settings
from src.core.logger.logger import logger as global_logger
from src.modules.youtube.application.use_cases.jobs.download_video_use_case import (
    DownloadVideoUseCase,
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

def download_videos_job():
    global_logger.info("Starting video download process...")

    repo = YoutubeContentRepository(logger=global_logger)
    service = YoutubeContentService(repository=repo, logger=global_logger)
    scraper = YouTubeScraperService(logger=global_logger)
    use_case = DownloadVideoUseCase(
        youtube_content_service=service,
        scraper=scraper,
        output_path=settings.DOWNLOAD_YOUTUBE_PATH,
        logger=global_logger,
    )

    try:
        while use_case.execute():
            pass
        global_logger.info("No more videos pending download. Finishing.")
    except Exception as e:
        global_logger.error(f"Download job aborted: {e}")


if __name__ == "__main__":
    download_videos_job()
