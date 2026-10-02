import signal
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Event

from sqlalchemy import select, text

from src.core.config.settings import settings
from src.core.database.connector import Session, engine
from src.modules.demograph.application.use_cases.pipeline import Pipeline
from src.modules.demograph.infrastructure.catalog import SqlCatalog, now
from src.modules.demograph.infrastructure.extraction import ChamberExtractor
from src.modules.demograph.infrastructure.models import RunModel, WorkerModel
from src.modules.demograph.presentation.dependencies.providers import get_graph

LOCK_ID = 73401953


def main() -> None:
    stopped = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopped.set())
    catalog = SqlCatalog()
    root = Path(settings.demograph_storage_path)
    root.mkdir(parents=True, exist_ok=True)
    graph = get_graph()
    graph.guard_adapter.stopped = stopped
    pipeline = Pipeline(catalog, ChamberExtractor(catalog, root, stopped), graph)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        if not connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID}
        ).scalar():
            raise RuntimeError("Another DemoGraph worker owns this database.")
        with Session.begin() as session:
            for row in session.scalars(select(RunModel).where(RunModel.status == "running")):
                row.status = "queued"
            if session.get(WorkerModel, "worker") is None:
                session.add(WorkerModel(id="worker"))
        future: Future[None] | None = None
        with ThreadPoolExecutor(max_workers=1) as executor:
            try:
                while not stopped.is_set():
                    # This dedicated connection must keep the session-level advisory lock.
                    owns_lock = connection.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' "
                            "AND pid = pg_backend_pid() AND objid = :key AND granted)"
                        ),
                        {"key": LOCK_ID},
                    ).scalar()
                    if not owns_lock:
                        raise RuntimeError("DemoGraph worker lock was lost.")
                    with Session.begin() as session:
                        heartbeat = session.get(WorkerModel, "worker")
                        assert heartbeat is not None
                        heartbeat.heartbeat_at = now()
                        if future is None or future.done():
                            if future is not None:
                                future.result()
                            pending = session.scalar(
                                select(RunModel)
                                .where(RunModel.status == "queued")
                                .order_by(RunModel.created_at)
                                .limit(1)
                                .with_for_update(skip_locked=True)
                            )
                            run_id = pending.id if pending else None
                            if pending:
                                pending.status = "running"
                            future = None
                        else:
                            run_id = None
                    if run_id:
                        future = executor.submit(pipeline.execute, run_id)
                    stopped.wait(2)
            finally:
                stopped.set()
                executor.shutdown(wait=True)
                with Session.begin() as session:
                    heartbeat = session.get(WorkerModel, "worker")
                    if heartbeat:
                        heartbeat.heartbeat_at = None
                if not connection.invalidated:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})


if __name__ == "__main__":
    main()
