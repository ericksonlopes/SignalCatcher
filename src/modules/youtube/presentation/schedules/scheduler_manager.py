from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from src.core.database.connector import engine
from src.core.logger.logger import logger
from src.modules.youtube.presentation.schedules.jobs.youtube_download_job import (
    download_videos_job,
)
from src.modules.youtube.presentation.schedules.jobs.youtube_extract_metadata_job import (
    extract_metadata_job,
)
from src.modules.youtube.presentation.schedules.jobs.youtube_monitor_channels_job import (
    youtube_monitor_channels_job,
)
from src.modules.youtube.presentation.schedules.jobs.youtube_process_errors_job import (
    process_errors_job,
)

# Job ids that no longer exist. They stay in the SQLAlchemyJobStore across restarts,
# so they have to be deleted explicitly: otherwise the old entry keeps firing its
# still-importable function alongside the new job, monitoring every channel twice.
LEGACY_JOB_IDS = ("daily_youtube_capture_job",)

# The stage jobs used to be called synchronously from inside the monitor job, which
# meant a single 30-minute slot had to fit channel monitoring plus metadata extraction
# plus every pending download. They are independent now, each with its own cadence.
#
# `max_instances=1` keeps a long run from overlapping itself; `coalesce=True` collapses
# runs missed while the process was down into a single catch-up instead of a burst; and
# `misfire_grace_time` bounds how late a missed run may still start.
JOB_DEFINITIONS = (
    {
        "func": youtube_monitor_channels_job,
        "id": "youtube_monitor_channels",
        "minutes": 30,
        "misfire_grace_time": 300,
    },
    {
        "func": extract_metadata_job,
        "id": "youtube_extract_metadata",
        "minutes": 15,
        "misfire_grace_time": 300,
    },
    {
        # Downloads are the long pole: a single video can take hours, so this runs on a
        # wide interval and relies on max_instances=1 to skip a tick that is still busy.
        "func": download_videos_job,
        "id": "youtube_download_videos",
        "minutes": 60,
        "misfire_grace_time": 600,
    },
    {
        # Retrying errors re-downloads videos, so it stays deliberately infrequent.
        "func": process_errors_job,
        "id": "youtube_process_errors",
        "minutes": 360,
        "misfire_grace_time": 600,
    },
)


def _remove_legacy_jobs(scheduler: BackgroundScheduler) -> None:
    for job_id in LEGACY_JOB_IDS:
        try:
            scheduler.remove_job(job_id)
            logger.info(f"Removed stale scheduled job '{job_id}' from the job store.")
        except JobLookupError:
            # Expected on a store that never had the old id, or after the first cleanup.
            pass


def _register_jobs(scheduler: BackgroundScheduler) -> None:
    for definition in JOB_DEFINITIONS:
        scheduler.add_job(
            definition["func"],
            trigger="interval",
            minutes=definition["minutes"],
            id=definition["id"],
            max_instances=1,
            coalesce=True,
            misfire_grace_time=definition["misfire_grace_time"],
            replace_existing=True,
        )
        logger.info(
            f"Scheduled job '{definition['id']}' every {definition['minutes']} minute(s)."
        )


def start_scheduler() -> BackgroundScheduler:
    jobstores = {"default": SQLAlchemyJobStore(engine=engine)}

    scheduler = BackgroundScheduler(jobstores=jobstores)

    # Started paused so the cleanup and registration below finish before anything can
    # fire. Persisted jobs whose next run is already in the past would otherwise run
    # while we are still reconciling the schedule.
    scheduler.start(paused=True)
    _remove_legacy_jobs(scheduler)
    _register_jobs(scheduler)
    scheduler.resume()

    logger.info("🚀 Scheduler running in the background! Executing jobs periodically.")

    return scheduler
