from datetime import datetime, timezone

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from src.infrastructure.loggers.logger import logger
from src.infrastructure.repositories.connector import engine
from src.presentation.schedules.jobs.daily_youtube_capture_job import daily_youtube_capture_job


def start_scheduler() -> BackgroundScheduler:
    jobstores = {'default': SQLAlchemyJobStore(engine=engine)}

    scheduler = BackgroundScheduler(jobstores=jobstores)

    # Runs every day at 3 AM
    scheduler.add_job(
        daily_youtube_capture_job,
        trigger='cron',
        hour=3,
        minute=0,
        id='daily_youtube_capture_job',
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc)
    )

    logger.info("🚀 Scheduler running in the background! Executing now, and then daily at 03:00.")
    scheduler.start()

    return scheduler
