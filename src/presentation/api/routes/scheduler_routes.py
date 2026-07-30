from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, HTTPException, Request, status, BackgroundTasks

from src.infrastructure.loggers.logger import logger
from src.presentation.schedules.jobs.daily_youtube_capture_job import daily_youtube_capture_job

router = APIRouter()


@router.post("/jobs/daily-youtube-capture/execute", status_code=status.HTTP_202_ACCEPTED)
def execute_daily_youtube_capture(background_tasks: BackgroundTasks):
    """
    Executes the daily_youtube_capture_job directly in the background.
    """
    background_tasks.add_task(daily_youtube_capture_job)
    logger.info("⚡ Background task for daily_youtube_capture_job triggered via API.")
    return {"message": "daily_youtube_capture_job execution started in the background."}


@router.post("/jobs/{job_id}/run", status_code=status.HTTP_200_OK)
def trigger_job(job_id: str, request: Request):
    """
    Manually triggers a scheduled job by its ID.
    Example: POST /api/scheduler/jobs/daily_capture_routine/run
    """
    scheduler: BackgroundScheduler = request.app.state.scheduler

    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found in the scheduler."
        )

    job.modify(next_run_time=datetime.now(timezone.utc))
    logger.info(f"⚡ Job '{job_id}' manually triggered.")

    return {"message": f"Job '{job_id}' triggered successfully."}
