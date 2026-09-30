from collections.abc import Callable
from datetime import datetime, timezone
from threading import Lock
from time import monotonic

from apscheduler.schedulers.background import BackgroundScheduler

from src.core.database.connector import Session
from src.core.database.job_control import JobControlRepository
from src.core.logger.logger import logger
from src.modules.youtube.presentation.schedules.jobs.youtube_delete_contents_job import (
    delete_contents_job,
)
from src.modules.youtube.presentation.schedules.jobs.youtube_download_job import download_videos_job
from src.modules.youtube.presentation.schedules.jobs.youtube_extract_and_download_job import (
    extract_and_download_job,
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
from src.modules.youtube.presentation.schedules.jobs.youtube_promote_scheduled_job import (
    promote_scheduled_job,
)

# Definitions live in code; durable requests and telemetry live in PostgreSQL.
# Only the dedicated worker owns this in-memory scheduler.
JOB_DEFINITIONS: dict[str, tuple[Callable[[], None], int | None]] = {
    "youtube_monitor_channels": (youtube_monitor_channels_job, 30),
    "youtube_extract_and_download": (extract_and_download_job, 15),
    "youtube_process_errors": (process_errors_job, 30),
    "youtube_promote_scheduled": (promote_scheduled_job, 30),
    "youtube_delete_contents": (delete_contents_job, 30),
    "youtube_extract_metadata": (extract_metadata_job, None),
    "youtube_download_videos": (download_videos_job, None),
}
_pipeline_lock = Lock()
_monitor_lock = Lock()


def _run_job(job_id: str) -> None:
    # Monitoring can run alongside media work; media operations share one lane.
    gate = _monitor_lock if job_id == "youtube_monitor_channels" else _pipeline_lock
    if not gate.acquire(blocking=False):
        with Session.begin() as session:
            JobControlRepository(session).request(job_id)
        return
    started = monotonic()
    error = None
    did_start = False
    try:
        with Session.begin() as session:
            did_start = JobControlRepository(session).start(job_id)
        if not did_start:
            return
        JOB_DEFINITIONS[job_id][0]()
    except Exception as exc:
        error = str(exc)
        logger.error(f"Job {job_id} failed: {exc}")
    finally:
        try:
            if did_start:
                with Session.begin() as session:
                    JobControlRepository(session).finish(job_id, monotonic() - started, error)
        finally:
            gate.release()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    for job_id, (_, minutes) in JOB_DEFINITIONS.items():
        options = {} if minutes is not None else {"next_run_time": None}
        scheduler.add_job(
            _run_job,
            args=[job_id],
            trigger="interval",
            minutes=minutes or 1440,
            id=job_id,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
            **options,
        )
    scheduler.start()
    return scheduler


def dispatch_requests(scheduler: BackgroundScheduler, pending: list[str]) -> None:
    for job_id in pending:
        gate = _monitor_lock if job_id == "youtube_monitor_channels" else _pipeline_lock
        if not gate.locked():
            scheduler.modify_job(job_id, next_run_time=datetime.now(timezone.utc))
