import logging
from typing import Any

from src.modules.demograph.domain.interfaces.catalog import Catalog
from src.modules.demograph.domain.interfaces.loader import Loader
from src.modules.demograph.domain.interfaces.storage import ExtractionStorage

logger = logging.getLogger(__name__)


class DeleteExtraction:
    def __init__(self, catalog: Catalog, graph: Loader, storage: ExtractionStorage) -> None:
        self.catalog, self.graph, self.storage = catalog, graph, storage

    def execute(self, extraction_id: str) -> dict[str, Any]:
        plan = self.catalog.begin_delete(extraction_id)
        try:
            self.storage.validate_deletion(extraction_id, plan["artifacts"])
            if not plan["graph_deleted"]:
                if plan["may_have_graph"]:
                    self.graph.delete_extraction(extraction_id, plan["run_ids"])
                self.catalog.progress(extraction_id, graph_deleted=True)
            self.storage.delete_extraction(extraction_id)
            self.catalog.finish_delete(extraction_id)
        except Exception:
            logger.exception("Failed to delete DemoGraph extraction %s", extraction_id)
            self.catalog.update(
                extraction_id, status="delete_failed", stage="delete", schema_stale=True
            )
            raise
        try:
            if plan["may_have_graph"]:
                self.catalog.save_schema(None, self.graph.schema())
        except Exception:
            logger.exception("Schema refresh failed after extraction deletion")
        return {"id": extraction_id, "status": "deleted", "files": len(plan["artifacts"])}
