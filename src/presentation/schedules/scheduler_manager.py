from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from src.infrastructure.loggers.logger import logger
from src.infrastructure.repositories.connector import engine
from src.presentation.schedules.jobs.youtube_monitor_channels_job import (
    youtube_monitor_channels_job,
)


def start_scheduler() -> BackgroundScheduler:
    jobstores = {'default': SQLAlchemyJobStore(engine=engine)}

    scheduler = BackgroundScheduler(jobstores=jobstores)

    scheduler.add_job(
        youtube_monitor_channels_job,
        trigger='interval',
        minutes=30,
        id='daily_youtube_capture_job',
        replace_existing=True
    )

    logger.info("🚀 Scheduler running in the background! Executing jobs periodically.")
    scheduler.start()

    return scheduler
