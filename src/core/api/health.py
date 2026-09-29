from datetime import datetime, timezone

from sqlalchemy import text

from src.core.config.settings import settings
from src.core.database.connector import Session
from src.core.database.job_control import WORKER_ID, JobControlModel


def readiness() -> dict[str, bool]:
    checks = {"database": False, "worker": False}
    try:
        with Session() as session:
            session.execute(text("SELECT 1"))
            checks["database"] = True
            worker = session.get(JobControlModel, WORKER_ID)
            if worker and worker.heartbeat_at:
                age = (datetime.now(timezone.utc) - worker.heartbeat_at).total_seconds()
                checks["worker"] = 0 <= age <= settings.WORKER_HEARTBEAT_MAX_AGE
    except Exception:
        # Health responses must not disclose credentials or internal database errors.
        pass
    return checks
