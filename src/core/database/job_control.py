from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from src.core.database.connector import Base

JOB_IDS = frozenset(
    {
        "youtube_monitor_channels",
        "youtube_extract_and_download",
        "youtube_extract_metadata",
        "youtube_download_videos",
        "youtube_process_errors",
        "youtube_promote_scheduled",
        "youtube_delete_contents",
    }
)
WORKER_ID = "__worker__"


class JobControlModel(Base):
    __tablename__ = "job_control"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    pending: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    running: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_duration_seconds: Mapped[float | None] = mapped_column(Float)
    last_error: Mapped[str | None] = mapped_column(String)
    runs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class JobControlRepository:
    """Durable coalesced requests and worker/job telemetry, in the caller's transaction."""

    def __init__(self, session: Session):
        self.session = session

    def request(self, job_id: str) -> None:
        if job_id not in JOB_IDS:
            raise ValueError("Unknown job.")
        now = datetime.now(timezone.utc)
        statement = insert(JobControlModel).values(id=job_id, pending=True, requested_at=now)
        self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[JobControlModel.id],
                set_={"pending": True, "requested_at": now},
            )
        )

    def initialize(self) -> None:
        for job_id in JOB_IDS | {WORKER_ID}:
            self.session.execute(insert(JobControlModel).values(id=job_id).on_conflict_do_nothing())
        # The worker holds the singleton advisory lock before recovering interrupted jobs.
        for model in self.session.query(JobControlModel).filter_by(running=True):
            model.running = False
            if model.id in JOB_IDS:
                model.pending = True
                model.last_error = "Worker stopped before completing the previous run."
                model.failures += 1
        self.session.flush()

    def heartbeat(self) -> None:
        self.session.query(JobControlModel).filter_by(id=WORKER_ID).update(
            {"heartbeat_at": datetime.now(timezone.utc)}
        )

    def pending_jobs(self) -> list[str]:
        return [
            row.id
            for row in self.session.query(JobControlModel)
            .filter_by(pending=True, running=False)
            .all()
            if row.id in JOB_IDS
        ]

    def start(self, job_id: str) -> bool:
        model = self.session.get(JobControlModel, job_id, with_for_update=True)
        if model is None or model.running:
            return False
        model.pending = False
        model.running = True
        model.started_at = datetime.now(timezone.utc)
        model.last_error = None
        self.session.flush()
        return True

    def finish(self, job_id: str, duration: float, error: str | None) -> None:
        model = self.session.get(JobControlModel, job_id, with_for_update=True)
        if model is None:
            return
        model.running = False
        model.finished_at = datetime.now(timezone.utc)
        model.last_duration_seconds = duration
        model.last_error = error
        model.runs += 1
        if error:
            model.failures += 1
        self.session.flush()
