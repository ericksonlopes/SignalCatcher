from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.modules.demograph.presentation.dependencies.catalog import CatalogDep
from src.modules.demograph.presentation.dtos.run_request import RunRequest

router = APIRouter()


@router.post("/runs", status_code=202)
def create_run(body: RunRequest, catalog: CatalogDep) -> dict[str, str]:
    parameters = body.model_dump(mode="json", exclude={"operation"})
    return {"id": catalog.create(body.operation, parameters), "status": "queued"}


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
        raise HTTPException(404, str(exc)) from exc


@router.post("/runs/{run_id}/retry", status_code=202)
def retry(run_id: str, catalog: CatalogDep) -> dict[str, str]:
    try:
        catalog.retry(run_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"id": run_id, "status": "queued"}


@router.post("/runs/{run_id}/cancel", status_code=202)
def cancel(run_id: str, catalog: CatalogDep) -> dict[str, str]:
    try:
        catalog.cancel(run_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"id": run_id, "status": "cancel_requested"}


@router.post("/extractions/{extraction_id}/load", status_code=202)
def load(extraction_id: str, catalog: CatalogDep) -> dict[str, str]:
    try:
        run_id = catalog.create("load", {}, extraction_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"id": run_id, "status": "queued"}
