from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, HTTPException, Request, status

from src.infrastructure.loggers.logger import logger

router = APIRouter()


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
