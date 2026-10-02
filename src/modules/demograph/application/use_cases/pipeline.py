import logging

from src.modules.demograph.domain.contracts import Catalog, Extractor, Loader

logger = logging.getLogger(__name__)


class Cancelled(Exception):
    """A cooperative cancellation was requested."""


class Pipeline:
    def __init__(self, catalog: Catalog, extractor: Extractor, loader: Loader) -> None:
        self.catalog = catalog
        self.extractor = extractor
        self.loader = loader

    def execute(self, run_id: str) -> None:
        logger.info(f"Starting execution for run_id: {run_id}")
        run = self.catalog.run(run_id)
        self.catalog.update(run_id, status="running", error=None)
        try:
            if run.cancel_requested:
                logger.warning(f"Run {run_id} cancelled before start.")
                raise Cancelled()
            if run.operation == "schema":
                logger.info(f"Run {run_id} is a schema operation.")
                self.catalog.update(run_id, stage="schema")
                self.catalog.save_schema(run_id, self.loader.schema(run_id))
                self.catalog.update(run_id, status="completed", stage="finished", finished=True)
                logger.info(f"Schema operation completed for run {run_id}.")
                return
            if run.operation != "load":
                logger.info(f"Starting extraction for run {run_id}.")
                self.extractor.extract(run)
                logger.info(f"Extraction finished for run {run_id}.")
            if self.catalog.run(run_id).cancel_requested:
                logger.warning(f"Run {run_id} cancelled after extraction.")
                raise Cancelled()
            if run.operation != "extract":
                logger.info(f"Starting load for run {run_id}.")
                self.loader.load(run)
                logger.info(f"Load finished for run {run_id}. Refreshing schema.")
                self.catalog.update(run_id, stage="schema")
                try:
                    self.catalog.save_schema(run_id, self.loader.schema(run_id))
                    logger.info(f"Schema refreshed for run {run_id}.")
                except Cancelled:
                    logger.warning(f"Run {run_id} cancelled during schema refresh.")
                    raise
                except Exception as exc:
                    logger.error(f"Schema refresh failed for run {run_id}: {exc}", exc_info=True)
                    self.catalog.issue(
                        run_id, "Schema refresh failed.", {"type": type(exc).__name__}
                    )
                    self.catalog.update(run_id, schema_stale=True)
            current = self.catalog.run(run_id)
            status = "completed_with_errors" if current.progress.get("issues", 0) else "completed"
            self.catalog.update(run_id, status=status, stage="finished", finished=True)
            logger.info(f"Execution finished for run {run_id} with status: {status}.")
        except Cancelled:
            logger.info(f"Execution gracefully cancelled for run {run_id}.")
            self.catalog.update(run_id, status="cancelled", finished=True)
        except Exception as exc:
            logger.exception(f"Unexpected error in pipeline for run {run_id}: {exc}")
            # Exception messages from HTTP/drivers may contain credentials or payloads.
            self.catalog.issue(run_id, "Pipeline stopped.", {"type": type(exc).__name__})
            self.catalog.update(run_id, status="failed", error=type(exc).__name__, finished=True)
