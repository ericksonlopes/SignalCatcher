from itertools import islice
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.core.config.settings import settings
from src.modules.demograph.infrastructure.catalog import SqlCatalog
from src.modules.demograph.infrastructure.storage.files import rows, safe_path
from src.modules.demograph.presentation.dependencies.catalog import CatalogDep

router = APIRouter()


def get_artifact(catalog: SqlCatalog, artifact_id: str) -> tuple[dict[str, Any], Path]:
    try:
        artifact = catalog.artifact(artifact_id)
        path = safe_path(Path(settings.demograph_storage_path), artifact["path"])
        if not path.is_file():
            raise LookupError("Artifact file is unavailable.")
        return artifact, path
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/artifacts/{artifact_id}/schema")
def artifact_schema(artifact_id: str, catalog: CatalogDep) -> dict[str, Any]:
    try:
        return catalog.artifact(artifact_id)["file_schema"]
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/artifacts/{artifact_id}/preview")
def preview(artifact_id: str, catalog: CatalogDep) -> dict[str, Any]:
    artifact, path = get_artifact(catalog, artifact_id)
    return {
        "items": list(islice(rows(path, artifact["metadata_json"]), 50)),
        "limit": 50,
        "total": artifact["records"],
    }


@router.get("/artifacts/{artifact_id}/download")
def download(artifact_id: str, catalog: CatalogDep) -> FileResponse:
    _, path = get_artifact(catalog, artifact_id)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")
