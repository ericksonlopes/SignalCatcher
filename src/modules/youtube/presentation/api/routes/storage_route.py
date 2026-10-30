from typing import Annotated, Literal, cast

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from src.core.config.settings import settings
from src.core.database.connector import Session
from src.core.database.job_control import JobControlRepository
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)
from src.modules.youtube.infrastructure.repositories.storage_repository import (
    StorageRepository,
)
from src.modules.youtube.infrastructure.services.drive_storage import DriveStorage

router = APIRouter()


class StorageSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["LOCAL", "DRIVE", "BOTH"] | None = None
    uploads_paused: bool | None = None
    max_upload_mib_per_second: float | None = Field(default=None, ge=0.1, le=10000)


class RestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_ids: list[str] = Field(min_length=1, max_length=100)


def request_storage_job() -> None:
    with Session.begin() as db:
        JobControlRepository(db).request("youtube_drive_backup")


@router.get("/storage-settings")
def storage_settings():
    return StorageRepository().settings()


@router.patch("/storage-settings")
def update_storage_settings(request: StorageSettingsUpdate):
    values = request.model_dump(exclude_unset=True)
    if values.get("mode") is None:
        values.pop("mode", None)
    if values.get("uploads_paused") is None:
        values.pop("uploads_paused", None)
    if values.get("mode") == "DRIVE":
        try:
            info = DriveStorage(
                settings.GOOGLE_DRIVE_OAUTH_PATH, settings.GOOGLE_DRIVE_FOLDER_ID
            ).inspect()
            StorageRepository().record_health(info)
        except Exception as exc:
            raise HTTPException(
                409, "Authorize Google Drive before selecting Drive-only mode."
            ) from exc
    result = StorageRepository().update_settings(values)
    request_storage_job()
    return result


@router.get("/drive-backups/summary")
def storage_summary():
    return StorageRepository().summary()


@router.get("/drive-backups")
def storage_transfers(
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    status: Annotated[
        str | None, Query(pattern="^(PENDING|RUNNING|COMPLETED|ERROR|MISSING_FILE)$")
    ] = None,
    search: str = "",
    location: Annotated[str | None, Query(pattern="^(LOCAL|DRIVE|BOTH|NONE)$")] = None,
):
    return StorageRepository().listing(page, limit, status, search, location)


@router.post("/drive-backups/retry-errors", status_code=202)
def retry_storage_errors():
    count = StorageRepository().retry_errors()
    request_storage_job()
    return {"queued": count}


@router.post("/drive-backups/restore", status_code=202)
def restore_storage(request: RestoreRequest):
    external_ids = set(request.external_ids)
    with Session() as db:
        contents = (
            db.query(YoutubeContentModel)
            .filter(
                YoutubeContentModel.external_id.in_(external_ids),
            )
            .all()
        )
        if len(contents) != len(external_ids):
            raise HTTPException(404, "One or more videos were not found.")
        if any(not item.drive_file_id or item.deletion_requested for item in contents):
            raise HTTPException(
                409, "A verified Drive copy is required for every selected video."
            )
        content_ids = [cast(int, item.id) for item in contents]
    try:
        for content_id in content_ids:
            StorageRepository().enqueue(content_id, "RESTORE", "BOTH")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    request_storage_job()
    return {"queued": len(content_ids)}


@router.get("/content/{external_id}/storage-history")
def storage_history(
    external_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    try:
        return StorageRepository().history(external_id, page, limit)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
