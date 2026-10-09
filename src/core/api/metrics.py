from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import func

from src.core.config.settings import settings
from src.core.database.connector import Session
from src.core.database.job_control import WORKER_ID, JobControlModel
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)

router = APIRouter()


@router.get("/metrics", tags=["Operations"])
def get_metrics():
    now = datetime.now(timezone.utc)
    with Session() as session:
        counts = (
            session.query(YoutubeContentModel.step, func.count(YoutubeContentModel.id))
            .group_by(YoutubeContentModel.step)
            .all()
        )
        oldest = (
            session.query(func.min(YoutubeContentModel.created_at))
            .filter(
                YoutubeContentModel.step.in_(
                    [
                        ContentStep.PENDING_METADATA_EXTRACTION,
                        ContentStep.PENDING_DOWNLOAD,
                        ContentStep.ERROR,
                        ContentStep.REPROCESSING,
                    ]
                ),
                YoutubeContentModel.deletion_requested.is_(False),
                YoutubeContentModel.attempt_count < settings.MAX_PROCESSING_ATTEMPTS,
            )
            .scalar()
        )
        if oldest and oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
        jobs = (
            session.query(JobControlModel)
            .filter(JobControlModel.id != WORKER_ID)
            .order_by(JobControlModel.id)
            .all()
        )
        expired = (
            session.query(YoutubeContentModel)
            .filter(YoutubeContentModel.lease_expires_at <= now)
            .count()
        )
        deletion_pending = (
            session.query(YoutubeContentModel).filter_by(deletion_requested=True).count()
        )
        retries_exhausted = (
            session.query(YoutubeContentModel)
            .filter(
                YoutubeContentModel.step.in_(
                    [ContentStep.ERROR, ContentStep.PENDING_METADATA_EXTRACTION]
                ),
                YoutubeContentModel.attempt_count >= settings.MAX_PROCESSING_ATTEMPTS,
            )
            .count()
        )
        deletion_exhausted = (
            session.query(YoutubeContentModel)
            .filter(
                YoutubeContentModel.deletion_requested.is_(True),
                YoutubeContentModel.deletion_attempt_count >= settings.MAX_PROCESSING_ATTEMPTS,
            )
            .count()
        )
        return {
            "content_counts": {step.name: count for step, count in counts},
            "oldest_queued_age_seconds": max(0, (now - oldest).total_seconds()) if oldest else 0,
            "expired_reservations": expired,
            "deletions_pending": deletion_pending,
            "retries_exhausted": retries_exhausted,
            "deletions_exhausted": deletion_exhausted,
            "jobs": [
                {
                    "id": job.id,
                    "pending": job.pending,
                    "running": job.running,
                    "requested_at": job.requested_at,
                    "started_at": job.started_at,
                    "finished_at": job.finished_at,
                    "last_duration_seconds": job.last_duration_seconds,
                    "last_error": job.last_error,
                    "runs": job.runs,
                    "failures": job.failures,
                }
                for job in jobs
            ],
        }
