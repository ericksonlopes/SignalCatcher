"""Dedicated scheduler process. The API never starts background media jobs."""

import signal
import sys
from threading import Event
from time import monotonic

from sqlalchemy import text

from src.core.api.health import readiness
from src.core.database.connector import Session, engine
from src.core.database.job_control import WORKER_ID, JobControlModel, JobControlRepository
from src.core.logger.logger import logger
from src.modules.youtube.infrastructure.unit_of_work import YoutubeUnitOfWork
from src.modules.youtube.presentation.schedules.scheduler_manager import (
    dispatch_requests,
    start_scheduler,
)

WORKER_LOCK_ID = 73401952


def main() -> None:
    stopped = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopped.set())
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        acquired = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": WORKER_LOCK_ID}
        ).scalar()
        if not acquired:
            raise RuntimeError("Another SignalCatcher worker already owns this database.")
        with Session.begin() as session:
            control = JobControlRepository(session)
            control.initialize()
            control.heartbeat()
        scheduler = start_scheduler()
        last_recovery = 0.0
        try:
            while not stopped.is_set():
                # Never renew readiness after losing the singleton connection/lock.
                owns_lock = connection.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' "
                        "AND pid = pg_backend_pid() AND objid = :key AND granted)"
                    ),
                    {"key": WORKER_LOCK_ID},
                ).scalar()
                if not owns_lock:
                    raise RuntimeError("Worker database lock was lost.")
                if monotonic() - last_recovery >= 30:
                    with YoutubeUnitOfWork(logger=logger) as uow:
                        recovered = uow.contents.recover_expired_leases()
                        uow.commit()
                    if recovered:
                        logger.warning(f"Recovered {recovered} expired content reservations.")
                    last_recovery = monotonic()
                with Session.begin() as session:
                    control = JobControlRepository(session)
                    control.heartbeat()
                    pending = control.pending_jobs()
                dispatch_requests(scheduler, pending)
                stopped.wait(2)
        finally:
            scheduler.shutdown(wait=True)
            with Session.begin() as session:
                session.query(JobControlModel).filter_by(id=WORKER_ID).update(
                    {"heartbeat_at": None}
                )
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": WORKER_LOCK_ID})


if __name__ == "__main__":
    if "--healthcheck" in sys.argv:
        sys.exit(0 if all(readiness().values()) else 1)
    main()
