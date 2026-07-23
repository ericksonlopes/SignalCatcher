from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from src.infrastructure.loggers.logger import logger
from src.infrastructure.repositories.connector import engine
from src.presentation.schedules.jobs.daily_youtube_capture_job import daily_youtube_capture_job


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

    logger.info("🚀 Scheduler running in the background! Executing now, and then every 30 minutes.")
    scheduler.start()

    return scheduler
