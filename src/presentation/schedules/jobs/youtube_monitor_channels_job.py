from src.application.use_cases.run_daily_capture_use_case import RunDailyCaptureUseCase
from src.config.settings import settings
from src.infrastructure.loggers.logger import logger as global_logger
from src.infrastructure.notifications.voice_monkey_notification import (
    VoiceMonkeyNotification,
)
from src.infrastructure.repositories.youtube_content_repository import (
    YoutubeContentRepository,
)
from src.infrastructure.repositories.youtube_monitored_channel_repository import YouTubeMonitoredChannelRepository
from src.infrastructure.services.monitor_task_service import MonitorTaskService
from src.infrastructure.services.youtube_scraper import YouTubeScraperService
from src.presentation.schedules.jobs.youtube_download_job import download_videos_job
from src.presentation.schedules.jobs.youtube_extract_metadata_job import (
    extract_metadata_job,
)


def youtube_monitor_channels_job():
    youtube_scraper = YouTubeScraperService(logger=global_logger)
    youtube_monitored_channel_repository = YouTubeMonitoredChannelRepository(logger=global_logger)
    youtube_content_repository = YoutubeContentRepository(logger=global_logger)

    monitor_service = MonitorTaskService(
        youtube_scraper=youtube_scraper,
        youtube_monitored_channel_repository=youtube_monitored_channel_repository,
        youtube_content_repository=youtube_content_repository,
        logger=global_logger
    )

    use_case = RunDailyCaptureUseCase(monitor_service=monitor_service)

    total_new_videos = use_case.execute()

    global_logger.info(
        f"Daily YouTube capture job finished. Total new videos detected: {total_new_videos}",
        context={"total_new_videos": total_new_videos}
    )
    extract_metadata_job()

    global_logger.info("Triggering automatic download process...")
    try:
        download_videos_job()
    except Exception as e:
        global_logger.error(f"Error during automatic download process: {e}")

    if total_new_videos > 0:
        global_logger.info(
            f"New videos detected ({total_new_videos}). Triggering VoiceMonkey notification...",
            context={"total_new_videos": total_new_videos, "monkey_id": settings.VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID}
        )
        notification = VoiceMonkeyNotification(
            api_token=settings.VOICE_MONKEY_API_TOKEN,
            monkey_id=settings.VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID,
            logger=global_logger
        )
        notification.send()
    else:
        global_logger.info("No new videos detected in daily capture. Skipping VoiceMonkey notification.")
