from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from threading import Event, local
from typing import TypeVar

from src.modules.demograph.infrastructure.extraction.transport import ChamberTransport

T = TypeVar("T")
R = TypeVar("R")


def resources(
    source: ChamberTransport,
    run_id: str,
    items: Iterable[T],
    operation: Callable[[ChamberTransport, T], R],
) -> Iterator[R]:
    """Bound pending work and join in-flight requests before leaving a stage."""
    aborted = Event()
    thread_state = local()
    transports: list[ChamberTransport] = []

    def execute(item: T) -> R:
        if not hasattr(thread_state, "transport"):
            transport = ChamberTransport(
                source.catalog,
                source.root,
                source.stopped,
                session_factory=source.session_factory,
                catalog_mutex=source.catalog_mutex,
                aborted=aborted,
            )
            thread_state.transport = transport
            transports.append(transport)
        transport = thread_state.transport
        transport.guard(run_id)
        return operation(transport, item)

    pool = ThreadPoolExecutor(max_workers=source.max_workers, thread_name_prefix="demograph-http")
    pending: set[Future[R]] = set()
    remaining = iter(items)
    try:
        for item in remaining:
            pending.add(pool.submit(execute, item))
            if len(pending) == source.max_workers:
                break
        while pending:
            source.guard(run_id)
            completed, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
            # Check every completed task before submitting more requests after an error.
            results = [future.result() for future in completed]
            for result in results:
                yield result
                try:
                    item = next(remaining)
                except StopIteration:
                    continue
                pending.add(pool.submit(execute, item))
    finally:
        aborted.set()
        for future in pending:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)
        for transport in transports:
            transport.http.close()
