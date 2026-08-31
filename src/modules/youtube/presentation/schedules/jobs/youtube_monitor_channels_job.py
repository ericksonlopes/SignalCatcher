from src.core.config.settings import settings
from src.core.logger.logger import logger as global_logger
from src.core.notifications.voice_monkey_notification import (
    VoiceMonkeyNotification,
)
from src.modules.youtube.application.use_cases.jobs.run_daily_capture_use_case import (
    RunDailyCaptureUseCase,
)
from src.modules.youtube.infrastructure.services.monitor_task_service import (
    MonitorTaskService,
)
from src.modules.youtube.infrastructure.services.youtube_scraper import (
    YouTubeScraperService,
)
from src.modules.youtube.infrastructure.unit_of_work import YoutubeUnitOfWork


def youtube_monitor_channels_job():
    """Detects newly published videos on every active channel.

    Only detection: metadata extraction and downloading are separate scheduled jobs.
    They used to be called synchronously from here, which meant one 30-minute slot had
    to fit channel monitoring plus every pending download. Since APScheduler allows a
    single instance per job, a long download run silently swallowed the next monitoring
    ticks.
    """
    youtube_scraper = YouTubeScraperService(logger=global_logger)

    monitor_service = MonitorTaskService(
        youtube_scraper=youtube_scraper,
        # One transaction per channel, opened inside the service.
        uow_factory=lambda: YoutubeUnitOfWork(logger=global_logger),
        logger=global_logger,
    )

    use_case = RunDailyCaptureUseCase(monitor_service=monitor_service)

    total_new_videos = use_case.execute()

    global_logger.info(
        f"Channel monitoring finished. Total new videos detected: {total_new_videos}. "
        f"They will be picked up by the metadata extraction and download jobs.",
        context={"total_new_videos": total_new_videos},
    )

    if total_new_videos > 0:
        global_logger.info(
            f"New videos detected ({total_new_videos}). Triggering VoiceMonkey notification...",
            context={
                "total_new_videos": total_new_videos,
                "monkey_id": settings.VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID,
            },
        )
        notification = VoiceMonkeyNotification(
            api_token=settings.VOICE_MONKEY_API_TOKEN,
            monkey_id=settings.VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID,
            logger=global_logger,
        )
        notification.send()
    else:
        global_logger.info(
            "No new videos detected in daily capture. Skipping VoiceMonkey notification."
        )
