from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, HTTPException, Request, status, BackgroundTasks

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

router = APIRouter()


@router.post("/jobs/extract-metadata/execute", status_code=status.HTTP_202_ACCEPTED)
def execute_extract_metadata(background_tasks: BackgroundTasks):
    """
    Executes the extract_metadata_job directly in the background.
    """
    background_tasks.add_task(extract_metadata_job)
    logger.info("⚡ Background task for extract_metadata_job triggered via API.")
    return {"message": "extract_metadata_job execution started in the background."}


@router.post("/jobs/download-videos/execute", status_code=status.HTTP_202_ACCEPTED)
def execute_download_videos(background_tasks: BackgroundTasks):
    """
    Executes the download_videos_job directly in the background.
    """
    background_tasks.add_task(download_videos_job)
    logger.info("⚡ Background task for download_videos_job triggered via API.")
    return {"message": "download_videos_job execution started in the background."}


@router.post("/jobs/process-errors/execute", status_code=status.HTTP_202_ACCEPTED)
def execute_process_errors(background_tasks: BackgroundTasks):
    """
    Executes the process_errors_job directly in the background.
    """
    background_tasks.add_task(process_errors_job)
    logger.info("⚡ Background task for process_errors_job triggered via API.")
    return {"message": "process_errors_job execution started in the background."}


@router.post(
    "/jobs/daily-youtube-capture/execute", status_code=status.HTTP_202_ACCEPTED
)
def execute_daily_youtube_capture(background_tasks: BackgroundTasks):
    """
    Executes the channel monitoring job directly in the background.

    The path keeps its original name so existing clients keep working, but the job only
    detects new videos now: extraction and download are triggered separately.
    """
    background_tasks.add_task(youtube_monitor_channels_job)
    logger.info("⚡ Background task for youtube_monitor_channels_job triggered via API.")
    return {
        "message": "youtube_monitor_channels_job execution started in the background."
    }


@router.post(
    "/jobs/{job_id}/run",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Job not found in the scheduler"}
    },
)
def trigger_job(job_id: str, request: Request):
    """
    Manually triggers a scheduled job by its ID.

    Valid ids: youtube_monitor_channels, youtube_extract_metadata,
    youtube_download_videos, youtube_process_errors, youtube_promote_scheduled.
    Example: POST /api/youtube/scheduler/jobs/youtube_download_videos/run
    """
    scheduler: BackgroundScheduler = request.app.state.scheduler

    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found in the scheduler.",
        )

    job.modify(next_run_time=datetime.now(timezone.utc))
    logger.info(f"⚡ Job '{job_id}' manually triggered.")

    return {"message": f"Job '{job_id}' triggered successfully."}
