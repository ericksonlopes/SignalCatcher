from typing import Any

from fastapi import APIRouter

from src.modules.demograph.presentation.dependencies.catalog import CatalogDep

router = APIRouter()


@router.get("/schema")
def schema(catalog: CatalogDep) -> dict[str, Any]:
    return catalog.schema()


@router.post("/schema/refresh", status_code=202)
def refresh_schema(catalog: CatalogDep) -> dict[str, str]:
    return {"id": catalog.create("schema", {"datasets": []}), "status": "queued"}
