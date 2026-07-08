from datetime import datetime, timezone

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from src.infrastructure.loggers.logger import logger
from src.infrastructure.repositories.connector import engine
from src.presentation.schedules.jobs.daily_youtube_capture_job import daily_youtube_capture_job


def start_scheduler() -> BackgroundScheduler:
    jobstores = {'default': SQLAlchemyJobStore(engine=engine)}

    scheduler = BackgroundScheduler(jobstores=jobstores)

    # Runs every 4 hours
    scheduler.add_job(
        daily_youtube_capture_job,
        trigger='interval',
        hours=4,
        id='daily_youtube_capture_job',
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc)
    )

    logger.info("🚀 Scheduler running in the background! Executing now, and then every 4 hours.")
    scheduler.start()

    return scheduler
