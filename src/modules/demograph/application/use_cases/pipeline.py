from src.modules.demograph.domain.contracts import Catalog, Extractor, Loader


class Cancelled(Exception):
    """A cooperative cancellation was requested."""


class Pipeline:
    def __init__(self, catalog: Catalog, extractor: Extractor, loader: Loader) -> None:
        self.catalog = catalog
        self.extractor = extractor
        self.loader = loader

    def execute(self, run_id: str) -> None:
        run = self.catalog.run(run_id)
        self.catalog.update(run_id, status="running", error=None)
        try:
            if run.cancel_requested:
                raise Cancelled()
            if run.operation == "schema":
                self.catalog.update(run_id, stage="schema")
                self.catalog.save_schema(run_id, self.loader.schema(run_id))
                self.catalog.update(run_id, status="completed", stage="finished", finished=True)
                return
            if run.operation != "load":
                self.extractor.extract(run)
            if self.catalog.run(run_id).cancel_requested:
                raise Cancelled()
            if run.operation != "extract":
                self.loader.load(run)
                self.catalog.update(run_id, stage="schema")
                try:
                    self.catalog.save_schema(run_id, self.loader.schema(run_id))
                except Cancelled:
                    raise
                except Exception as exc:
                    self.catalog.issue(
                        run_id, "Schema refresh failed.", {"type": type(exc).__name__}
                    )
                    self.catalog.update(run_id, schema_stale=True)
            current = self.catalog.run(run_id)
            status = "completed_with_errors" if current.progress.get("issues", 0) else "completed"
            self.catalog.update(run_id, status=status, stage="finished", finished=True)
        except Cancelled:
            self.catalog.update(run_id, status="cancelled", finished=True)
        except Exception as exc:
            # Exception messages from HTTP/drivers may contain credentials or payloads.
            self.catalog.issue(run_id, "Pipeline stopped.", {"type": type(exc).__name__})
            self.catalog.update(run_id, status="failed", error=type(exc).__name__, finished=True)
