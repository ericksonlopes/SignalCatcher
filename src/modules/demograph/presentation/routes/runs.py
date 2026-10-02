import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from src.modules.demograph.presentation.dependencies.catalog import CatalogDep
from src.modules.demograph.presentation.dependencies.pipeline import PipelineDep
from src.modules.demograph.presentation.dtos.run_request import RunRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/runs", status_code=202)
def create_run(
    body: RunRequest, catalog: CatalogDep, pipeline: PipelineDep, background: BackgroundTasks
) -> dict[str, str]:
    parameters = body.model_dump(mode="json", exclude={"operation"})
    try:
        run_id = catalog.create(body.operation, parameters, status="running")
        logger.info(f"Created run {run_id} with operation {body.operation}")
        background.add_task(pipeline.execute, run_id)
        return {"id": run_id, "status": "running"}
    except Exception as exc:
        logger.error(f"Failed to create run: {exc}", exc_info=True)
        raise HTTPException(500, "Internal server error") from exc


@router.get("/runs")
def runs(
    catalog: CatalogDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
) -> dict[str, Any]:
    return catalog.list_runs(page, page_size, status)


@router.get("/runs/{run_id}")
def run_detail(run_id: str, catalog: CatalogDep) -> dict[str, Any]:
    try:
        return catalog.detail(run_id)
    except LookupError as exc:
        logger.warning(f"Run {run_id} not found: {exc}")
        raise HTTPException(404, str(exc)) from exc


@router.post("/runs/{run_id}/retry", status_code=202)
def retry(
    run_id: str, catalog: CatalogDep, pipeline: PipelineDep, background: BackgroundTasks
) -> dict[str, str]:
    try:
        catalog.retry(run_id, status="running")
        logger.info(f"Retrying run {run_id}")
    except LookupError as exc:
        logger.warning(f"Run {run_id} not found for retry: {exc}")
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        logger.warning(f"Run {run_id} cannot be retried: {exc}")
        raise HTTPException(409, str(exc)) from exc
    background.add_task(pipeline.execute, run_id)
    return {"id": run_id, "status": "running"}


@router.post("/runs/{run_id}/cancel", status_code=202)
def cancel(run_id: str, catalog: CatalogDep) -> dict[str, str]:
    try:
        catalog.cancel(run_id)
        logger.info(f"Cancel requested for run {run_id}")
    except LookupError as exc:
        logger.warning(f"Run {run_id} not found for cancel: {exc}")
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        logger.warning(f"Run {run_id} cannot be cancelled: {exc}")
        raise HTTPException(409, str(exc)) from exc
    return {"id": run_id, "status": "cancel_requested"}


@router.post("/extractions/{extraction_id}/load", status_code=202)
def load(
    extraction_id: str, catalog: CatalogDep, pipeline: PipelineDep, background: BackgroundTasks
) -> dict[str, str]:
    try:
        run_id = catalog.create("load", {}, extraction_id, status="running")
        logger.info(f"Created load run {run_id} for extraction {extraction_id}")
    except LookupError as exc:
        logger.warning(f"Extraction {extraction_id} not found for load: {exc}")
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        logger.warning(f"Extraction {extraction_id} cannot be loaded: {exc}")
        raise HTTPException(409, str(exc)) from exc
    background.add_task(pipeline.execute, run_id)
    return {"id": run_id, "status": "running"}
