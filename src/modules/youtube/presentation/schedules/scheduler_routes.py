from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.core.database.job_control import JOB_IDS, JobControlRepository
from src.modules.youtube.presentation.api.dependencies import get_job_control

router = APIRouter()
JobControl = Annotated[JobControlRepository, Depends(get_job_control)]


def _queue(control: JobControlRepository, job_id: str) -> dict[str, str]:
    if job_id not in JOB_IDS:
        raise HTTPException(404, "Job not found.")
    control.request(job_id)
    return {"message": "Job execution queued.", "job_id": job_id}


@router.post("/jobs/extract-metadata/execute", status_code=202)
def execute_extract_metadata(control: JobControl):
    return _queue(control, "youtube_extract_metadata")


@router.post("/jobs/download-videos/execute", status_code=202)
def execute_download_videos(control: JobControl):
    return _queue(control, "youtube_download_videos")


@router.post("/jobs/extract-and-download/execute", status_code=202)
def execute_extract_and_download(control: JobControl):
    return _queue(control, "youtube_extract_and_download")


@router.post("/jobs/process-errors/execute", status_code=202)
def execute_process_errors(control: JobControl):
    return _queue(control, "youtube_process_errors")


@router.post("/jobs/daily-youtube-capture/execute", status_code=202)
def execute_daily_youtube_capture(control: JobControl):
    return _queue(control, "youtube_monitor_channels")


@router.post("/jobs/{job_id}/run", status_code=202)
def trigger_job(job_id: str, control: JobControl):
    return _queue(control, job_id)
