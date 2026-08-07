from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from src.infrastructure.loggers.logger import logger
from src.infrastructure.repositories.connector import engine
from src.presentation.schedules.jobs.youtube_capture_job import (
    daily_youtube_capture_job,
)
from src.presentation.schedules.jobs.youtube_extract_metadata_job import (
    extract_metadata_job,
)

def start_scheduler() -> BackgroundScheduler:
    jobstores = {'default': SQLAlchemyJobStore(engine=engine)}

    scheduler = BackgroundScheduler(jobstores=jobstores)

    scheduler.add_job(
        daily_youtube_capture_job,
        trigger='interval',
        minutes=30,
        id='daily_youtube_capture_job',
        replace_existing=True
    )

    scheduler.add_job(
        extract_metadata_job,
        trigger="interval",
        minutes=15,  # Runs every 15 minutes to process pending extractions
        id="extract_metadata_job",
        replace_existing=True,
    )

    logger.info("🚀 Scheduler running in the background! Executing jobs periodically.")
    scheduler.start()

    return scheduler
