from typing import Any

from fastapi import APIRouter, BackgroundTasks

from src.modules.demograph.presentation.dependencies.catalog import CatalogDep
from src.modules.demograph.presentation.dependencies.pipeline import PipelineDep

router = APIRouter()


@router.get("/schema")
def schema(catalog: CatalogDep) -> dict[str, Any]:
    return catalog.schema()


@router.post("/schema/refresh", status_code=202)
def refresh_schema(
    catalog: CatalogDep, pipeline: PipelineDep, background: BackgroundTasks
) -> dict[str, str]:
    run_id = catalog.create("schema", {"datasets": []}, status="running")
    background.add_task(pipeline.execute, run_id)
    return {"id": run_id, "status": "running"}
