from src.application.use_cases.run_daily_capture_use_case import RunDailyCaptureUseCase
from src.infrastructure.loggers.logger import logger as global_logger
from src.infrastructure.repositories.content_repository import ContentRepository
from src.infrastructure.repositories.monitored_source_repository import MonitoredSourceRepository
from src.infrastructure.services.monitor_task_service import MonitorTaskService
from src.infrastructure.services.youtube_scraper import YouTubeScraperService
from src.infrastructure.notifications.voice_monkey_notification import VoiceMonkeyNotification
from src.config.settings import settings


def daily_youtube_capture_job():
    youtube_scraper = YouTubeScraperService(logger=global_logger)
    monitored_source_repository = MonitoredSourceRepository(logger=global_logger)
    content_repository = ContentRepository(logger=global_logger)

    monitor_service = MonitorTaskService(
        youtube_scraper=youtube_scraper,
        monitored_source_repository=monitored_source_repository,
        content_repository=content_repository,
        logger=global_logger
    )

    use_case = RunDailyCaptureUseCase(monitor_service=monitor_service)

    total_new_videos = use_case.execute()
    
    if total_new_videos > 0:
        notification = VoiceMonkeyNotification(
            api_token=settings.VOICE_MONKEY_API_TOKEN,
            monkey_id=settings.VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID,
            logger=global_logger
        )
        notification.send()
