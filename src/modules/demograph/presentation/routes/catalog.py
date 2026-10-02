from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.modules.demograph.presentation.dependencies.catalog import CatalogDep

router = APIRouter()


@router.get("/datasets")
def datasets(catalog: CatalogDep, version_page: int = Query(1, ge=1)) -> dict[str, Any]:
    return {"items": catalog.datasets(version_page)}


@router.get("/datasets/{dataset_id}")
def dataset(
    dataset_id: str, catalog: CatalogDep, version_page: int = Query(1, ge=1)
) -> dict[str, Any]:
    item = next((item for item in catalog.datasets(version_page) if item["id"] == dataset_id), None)
    if item is None:
        raise HTTPException(404, "Dataset not found.")
    return item
