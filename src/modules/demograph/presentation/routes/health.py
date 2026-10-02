from pathlib import Path
from typing import Any

from fastapi import APIRouter

from src.core.config.settings import settings
from src.modules.demograph.presentation.dependencies.catalog import CatalogDep

router = APIRouter()


@router.get("/health")
def health(catalog: CatalogDep) -> dict[str, Any]:
    root = Path(settings.demograph_storage_path)
    neo4j = "unconfigured"
    if settings.DEMOGRAPH_NEO4J_URI and settings.DEMOGRAPH_NEO4J_PASSWORD:
        from src.modules.demograph.presentation.dependencies.providers import get_graph

        try:
            with get_graph().driver() as driver:
                driver.verify_connectivity()
            neo4j = "online"
        except Exception:
            neo4j = "unavailable"
    return {"execution": "api", "storage": root.is_dir(), "neo4j": neo4j}
