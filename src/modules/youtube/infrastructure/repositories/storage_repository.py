from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, load_only

from src.core.database.connector import Session as DefaultSession
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.storage import TransferInterrupted
from src.modules.youtube.infrastructure.repositories.models.storage_model import (
    DriveBackupModel,
    StorageEventModel,
    StorageSettingsModel,
    StorageTransferModel,
)
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)

CONTENT_FIELDS = (
    "id",
    "external_id",
    "title",
    "origin",
    "url",
    "file_path",
    "staging_path",
    "storage_location",
    "storage_mode",
    "drive_file_id",
    "drive_url",
    "step",
)


def inventory_columns():
    # Raw yt-dlp JSON can be megabytes per video; inventory must never load it.
    return load_only(*(getattr(YoutubeContentModel, name) for name in CONTENT_FIELDS))


def now() -> datetime:
    return datetime.now(timezone.utc)


def event(
    db: Session,
    content_id: Any,
    action: str,
    details: str | None = None,
    previous: Any = None,
    location: Any = None,
) -> None:
    db.add(
        StorageEventModel(
            content_id=int(content_id),
            action=action,
            details=details,
            previous_location=str(previous) if previous is not None else None,
            new_location=str(location) if location is not None else None,
        )
    )


def record_download(db: Session, item: YoutubeContentModel) -> None:
    """Called by the content repository in the download's completion transaction."""
    mode = item.storage_mode or "LOCAL"
    previous = item.storage_location
    backup = db.get(DriveBackupModel, item.id)
    item.storage_location = "LOCAL" if item.file_path else "NONE"
    item.storage_verified_at = now()
    event(
        db,
        item.id,
        "LOCAL_SAVED" if item.file_path else "TEMPORARY_SAVED",
        previous=previous,
        location=item.storage_location,
    )
    if backup:
        backup.verified = False
        item.drive_file_id = item.drive_url = None
    if mode == "LOCAL":
        return
    relative = (item.file_path or item.staging_path or "").replace("\\", "/")
    relative = relative.removeprefix("/youtube/").removeprefix(".staging/")
    if backup is None:
        backup = DriveBackupModel(
            content_id=item.id,
            external_id=item.external_id,
            title=item.title,
            origin=item.origin,
            source_url=item.url,
            relative_path=relative,
        )
        db.add(backup)
    else:
        backup.relative_path = relative
        backup.verified = False
    task = db.scalar(
        select(StorageTransferModel).where(
            StorageTransferModel.content_id == item.id,
            StorageTransferModel.operation == "UPLOAD",
        )
    )
    if task is None:
        task = StorageTransferModel(content_id=item.id, operation="UPLOAD", mode=mode)
        db.add(task)
    elif task.status == "RUNNING":
        # A re-download invalidates an older transfer's reservation and source snapshot.
        task.lease_token = None
        task.lease_expires_at = None
    task.status = "PENDING"
    task.mode = mode
    task.attempts = 0
    task.session_uri = task.error = None
    task.bytes_transferred = 0
    task.total_bytes = item.storage_size or 0
    task.next_retry_at = None
    event(db, item.id, "UPLOAD_QUEUED")


class StorageRepository:
    def __init__(self, factory: Callable[[], Session] = DefaultSession):
        self.factory = factory

    @staticmethod
    def _settings(db: Session) -> StorageSettingsModel:
        item = db.get(StorageSettingsModel, 1)
        if item is None:
            item = StorageSettingsModel(id=1)
            db.add(item)
            db.flush()
        return item

    def settings(self) -> dict[str, Any]:
        with self.factory() as db, db.begin():
            item = self._settings(db)
            return {
                key: getattr(item, key)
                for key in (
                    "mode",
                    "uploads_paused",
                    "max_upload_mib_per_second",
                    "drive_ready",
                    "drive_info",
                    "last_error",
                    "checked_at",
                    "catalog_error",
                    "catalog_updated_at",
                )
            }

    def update_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        with self.factory() as db, db.begin():
            item = self._settings(db)
            for key, value in values.items():
                setattr(item, key, value)
        return self.settings()

    @staticmethod
    def _content(item: YoutubeContentModel) -> dict[str, Any]:
        return {key: getattr(item, key) for key in CONTENT_FIELDS}

    def candidates(self) -> list[dict[str, Any]]:
        with self.factory() as db:
            backups: dict[Any, DriveBackupModel] = {
                item.content_id: item for item in db.scalars(select(DriveBackupModel))
            }
            return [
                self._content(item)
                | {
                    "drive_md5": backups[item.id].md5 if item.id in backups else None,
                    "drive_size": backups[item.id].size if item.id in backups else None,
                }
                for item in db.scalars(
                    select(YoutubeContentModel)
                    .options(inventory_columns())
                    .where(
                        YoutubeContentModel.step != ContentStep.DELETED,
                        YoutubeContentModel.deletion_requested.is_(False),
                        YoutubeContentModel.lease_token.is_(None),
                    )
                    .order_by(YoutubeContentModel.id)
                )
            ]

    def observe(self, content_id: int, local: str | None, remote: bool | None) -> None:
        with self.factory() as db, db.begin():
            item = db.get(YoutubeContentModel, content_id, with_for_update=True)
            if item is None or item.lease_token or item.deletion_requested:
                return
            backup = db.get(DriveBackupModel, content_id)
            if backup and remote is not None:
                backup.verified = remote
            has_remote = bool(backup and backup.verified)
            location = (
                "BOTH"
                if local and has_remote
                else ("LOCAL" if local else "DRIVE" if has_remote else "NONE")
            )
            previous = item.storage_location
            if previous != location:
                event(
                    db,
                    content_id,
                    "LOCATION_CHANGED",
                    previous=previous,
                    location=location,
                )
            item.storage_location = location
            item.storage_verified_at = now()
            item.file_path = local
            if backup and backup.verified:
                item.drive_file_id = backup.file_id
                item.drive_url = backup.web_url
            elif remote is not None:
                item.drive_file_id = item.drive_url = None

    def reconcile(self, observations: list[dict[str, Any]], mode: str) -> None:
        if not observations:
            return
        with self.factory() as db, db.begin():
            contents = {
                cast(int, item.id): cast(Any, item)
                for item in db.scalars(
                    select(YoutubeContentModel)
                    .options(inventory_columns())
                    .where(
                        YoutubeContentModel.id.in_([row["id"] for row in observations]),
                        YoutubeContentModel.lease_token.is_(None),
                        YoutubeContentModel.deletion_requested.is_(False),
                    )
                    .with_for_update(skip_locked=True)
                )
            }
            backups = {
                item.content_id: item for item in db.scalars(select(DriveBackupModel))
            }
            uploads = {
                item.content_id: item
                for item in db.scalars(
                    select(StorageTransferModel).where(
                        StorageTransferModel.operation == "UPLOAD"
                    )
                )
            }
            for row in observations:
                item = contents.get(row["id"])
                if item is None:
                    continue
                backup = backups.get(item.id)
                remote = row.get("remote")
                if backup and remote is not None:
                    backup.verified = remote
                local = row.get("local")
                verified = bool(backup and backup.verified)
                location = (
                    "BOTH"
                    if local and verified
                    else ("LOCAL" if local else "DRIVE" if verified else "NONE")
                )
                if item.storage_location != location:
                    event(
                        db,
                        item.id,
                        "LOCATION_CHANGED",
                        previous=item.storage_location,
                        location=location,
                    )
                item.storage_location = location
                item.storage_verified_at = now()
                item.file_path = local
                item.storage_size = row.get("size")
                if verified and backup:
                    item.drive_file_id = backup.file_id
                    item.drive_url = backup.web_url
                elif remote is not None:
                    item.drive_file_id = item.drive_url = None
                if (
                    mode == "LOCAL"
                    or verified
                    or not row.get("source")
                    or not row.get("eligible", True)
                ):
                    continue
                if backup is None:
                    backup = DriveBackupModel(
                        content_id=item.id,
                        external_id=item.external_id,
                        title=item.title,
                        origin=item.origin,
                        source_url=item.url,
                        relative_path=row["relative"],
                    )
                    db.add(backup)
                    backups[item.id] = backup
                upload = uploads.get(item.id)
                if upload is None:
                    upload = StorageTransferModel(
                        content_id=item.id,
                        operation="UPLOAD",
                        mode=item.storage_mode or mode,
                        total_bytes=row["size"] or 0,
                    )
                    db.add(upload)
                    uploads[item.id] = upload
                    event(db, item.id, "UPLOAD_QUEUED")
                elif upload.status in {"COMPLETED", "MISSING_FILE"}:
                    upload.status = "PENDING"
                    upload.attempts = 0
                    upload.next_retry_at = None
                    upload.error = None
                    event(db, item.id, "UPLOAD_QUEUED")

    def enqueue(self, content_id: int, operation: str, mode: str) -> None:
        with self.factory() as db, db.begin():
            item = db.get(YoutubeContentModel, content_id, with_for_update=True)
            if item is None or item.deletion_requested:
                return
            backup = db.get(DriveBackupModel, content_id)
            if operation == "UPLOAD" and backup and backup.verified:
                return
            if operation == "RESTORE" and not (backup and backup.verified):
                raise ValueError(
                    "A verified Drive copy is required to restore this video."
                )
            if backup is None:
                relative = (item.file_path or item.staging_path or "").replace(
                    "\\", "/"
                )
                relative = relative.removeprefix("/youtube/").removeprefix(".staging/")
                if not relative:
                    return
                backup = DriveBackupModel(
                    content_id=item.id,
                    external_id=item.external_id,
                    title=item.title,
                    origin=item.origin,
                    source_url=item.url,
                    relative_path=relative,
                )
                db.add(backup)
            transfer = db.scalar(
                select(StorageTransferModel).where(
                    StorageTransferModel.content_id == content_id,
                    StorageTransferModel.operation == operation,
                )
            )
            if transfer is None:
                db.add(
                    StorageTransferModel(
                        content_id=content_id, operation=operation, mode=mode
                    )
                )
                event(db, content_id, operation + "_QUEUED")
            elif transfer.status in {"COMPLETED", "MISSING_FILE"}:
                transfer.status = "PENDING"
                transfer.mode = mode
                transfer.attempts = 0
                transfer.error = None
                transfer.next_retry_at = None
                event(db, content_id, operation + "_QUEUED")

    def claim(self) -> dict[str, Any] | None:
        with self.factory() as db, db.begin():
            config = self._settings(db)
            # A dead worker's reservation is recovered without losing its upload session.
            db.query(StorageTransferModel).filter(
                StorageTransferModel.status == "RUNNING",
                StorageTransferModel.lease_expires_at < now(),
            ).update(
                {"status": "PENDING", "lease_token": None, "lease_expires_at": None}
            )
            query = (
                select(StorageTransferModel)
                .join(
                    YoutubeContentModel,
                    YoutubeContentModel.id == StorageTransferModel.content_id,
                )
                .where(
                    StorageTransferModel.status.in_(["PENDING", "ERROR"]),
                    StorageTransferModel.attempts < 5,
                    or_(
                        StorageTransferModel.next_retry_at.is_(None),
                        StorageTransferModel.next_retry_at <= now(),
                    ),
                    YoutubeContentModel.deletion_requested.is_(False),
                    YoutubeContentModel.lease_token.is_(None),
                )
            )
            if config.uploads_paused or config.mode == "LOCAL":
                query = query.where(StorageTransferModel.operation == "RESTORE")
            task = db.scalar(
                query.order_by(
                    StorageTransferModel.operation.desc(), StorageTransferModel.id
                ).with_for_update(skip_locked=True)
            )
            if task is None:
                return None
            task.status = "RUNNING"
            task.lease_token = str(uuid4())
            task.lease_expires_at = now() + timedelta(seconds=300)
            task.attempts += 1
            task.updated_at = now()
            item = db.get(YoutubeContentModel, task.content_id)
            backup = db.get(DriveBackupModel, task.content_id)
            assert item is not None and backup is not None
            event(db, task.content_id, task.operation + "_STARTED")
            return {
                **self._content(item),
                "content_id": item.id,
                "task_id": task.id,
                "operation": task.operation,
                "mode": task.mode,
                "token": task.lease_token,
                "session_uri": task.session_uri,
                "file_id": backup.file_id,
                "relative_path": backup.relative_path,
                "md5": backup.md5,
                "size": backup.size,
                "remote_verified": backup.verified,
            }

    @staticmethod
    def _owned(db: Session, task: dict[str, Any]) -> StorageTransferModel:
        item = db.get(StorageTransferModel, task["task_id"], with_for_update=True)
        if (
            item is None
            or item.lease_token != task["token"]
            or item.status != "RUNNING"
        ):
            raise TransferInterrupted("Transfer reservation was lost.")
        expires = item.lease_expires_at
        if expires is None:
            raise TransferInterrupted("Transfer reservation expired.")
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now():
            raise TransferInterrupted("Transfer reservation expired.")
        return item

    def checkpoint(
        self, task: dict[str, Any], sent: int, total: int, session_uri: str | None
    ) -> None:
        with self.factory() as db, db.begin():
            transfer = self._owned(db, task)
            config = self._settings(db)
            transfer.bytes_transferred = sent
            transfer.total_bytes = total
            if session_uri is not None:
                transfer.session_uri = session_uri
            transfer.lease_expires_at = now() + timedelta(seconds=300)
            transfer.updated_at = now()
            paused = task["operation"] == "UPLOAD" and (
                config.uploads_paused or config.mode == "LOCAL"
            )
        if paused:
            raise TransferInterrupted("Uploads are paused.")

    def reserve_remote(self, task: dict[str, Any], file_id: str) -> None:
        with self.factory() as db, db.begin():
            self._owned(db, task)
            backup = db.get(DriveBackupModel, task["content_id"])
            assert backup is not None
            backup.file_id = file_id

    def finish(self, task: dict[str, Any], result: dict[str, Any]) -> None:
        with self.factory() as db, db.begin():
            transfer = self._owned(db, task)
            item = db.get(YoutubeContentModel, task["content_id"], with_for_update=True)
            backup = db.get(DriveBackupModel, task["content_id"])
            assert item is not None and backup is not None
            previous = item.storage_location
            if task["operation"] == "UPLOAD":
                backup.file_id = result["id"]
                backup.web_url = result.get("webViewLink")
                backup.size = int(result["size"])
                backup.md5 = result["md5Checksum"]
                backup.verified = True
                backup.completed_at = now()
                item.drive_file_id = backup.file_id
                item.drive_url = backup.web_url
                item.storage_location = "BOTH" if item.file_path else "DRIVE"
                if item.step == ContentStep.DOWNLOADED:
                    item.step = ContentStep.COMPLETED
            else:
                item.file_path = result["file_path"]
                item.storage_location = "BOTH" if backup.verified else "LOCAL"
            item.storage_verified_at = now()
            transfer.status = "COMPLETED"
            transfer.bytes_transferred = transfer.total_bytes = backup.size
            transfer.error = transfer.session_uri = transfer.lease_token = None
            transfer.lease_expires_at = transfer.next_retry_at = None
            transfer.updated_at = now()
            event(
                db,
                item.id,
                task["operation"] + "_COMPLETED",
                previous=previous,
                location=item.storage_location,
            )

    def staging_removed(self, content_id: int) -> None:
        with self.factory() as db, db.begin():
            item = db.get(YoutubeContentModel, content_id, with_for_update=True)
            if item and item.staging_path:
                item.staging_path = None
                event(db, content_id, "TEMPORARY_REMOVED")
                task = db.scalar(
                    select(StorageTransferModel).where(
                        StorageTransferModel.content_id == content_id,
                        StorageTransferModel.operation == "UPLOAD",
                        StorageTransferModel.status == "COMPLETED",
                    )
                )
                if task:
                    task.error = None

    def staging_cleanup_failed(self, content_id: int, error: str) -> None:
        with self.factory() as db, db.begin():
            task = db.scalar(
                select(StorageTransferModel).where(
                    StorageTransferModel.content_id == content_id,
                    StorageTransferModel.operation == "UPLOAD",
                    StorageTransferModel.status == "COMPLETED",
                )
            )
            if task:
                task.error = (
                    "Drive copy verified; temporary cleanup failed: " + error[:1000]
                )
            event(db, content_id, "TEMPORARY_REMOVE_FAILED", error[:1000])

    def fail(self, task: dict[str, Any], error: str, blocked: bool = False) -> None:
        with self.factory() as db, db.begin():
            item = self._owned(db, task)
            item.status = (
                "MISSING_FILE" if error.startswith("Missing source:") else "ERROR"
            )
            item.error = error[:2000]
            if any(
                marker in error.lower()
                for marker in (
                    "checksum",
                    "source changed",
                    "source file changed",
                    "session expired",
                )
            ):
                item.session_uri = None
                item.bytes_transferred = 0
            item.next_retry_at = now() + timedelta(
                seconds=min(86400, 300 * 2**item.attempts)
            )
            item.lease_token = None
            item.lease_expires_at = None
            item.updated_at = now()
            event(db, item.content_id, item.operation + "_FAILED", item.error)
            if blocked:
                self._settings(db).last_error = error[:2000]

    def release(self, task: dict[str, Any]) -> None:
        with self.factory() as db, db.begin():
            item = self._owned(db, task)
            item.status = "PENDING"
            item.attempts = max(0, item.attempts - 1)
            item.lease_token = None
            item.lease_expires_at = None

    def retry_errors(self) -> int:
        with self.factory() as db, db.begin():
            items = db.scalars(
                select(StorageTransferModel)
                .where(StorageTransferModel.status.in_(["ERROR", "MISSING_FILE"]))
                .with_for_update()
            ).all()
            for item in items:
                item.status = "PENDING"
                item.attempts = 0
                item.error = None
                item.next_retry_at = None
                event(db, item.content_id, item.operation + "_RETRY_QUEUED")
            return len(items)

    def record_health(self, info: dict[str, Any], error: str | None = None) -> None:
        with self.factory() as db, db.begin():
            item = self._settings(db)
            item.drive_ready = error is None
            item.last_error = error
            item.checked_at = now()
            if info:
                item.drive_info = info

    def catalog(self) -> list[dict[str, Any]]:
        with self.factory() as db:
            return [
                {
                    key: getattr(item, key)
                    for key in (
                        "external_id",
                        "title",
                        "origin",
                        "source_url",
                        "relative_path",
                        "file_id",
                        "web_url",
                        "size",
                        "md5",
                    )
                }
                | {
                    "completed_at": (
                        item.completed_at.isoformat() if item.completed_at else None
                    )
                }
                for item in db.scalars(
                    select(DriveBackupModel)
                    .where(DriveBackupModel.verified.is_(True))
                    .order_by(DriveBackupModel.content_id)
                )
            ]

    def catalog_result(self, error: str | None) -> None:
        with self.factory() as db, db.begin():
            item = self._settings(db)
            item.catalog_error = error
            if error is None:
                item.catalog_updated_at = now()

    def summary(self) -> dict[str, Any]:
        result = self.settings()
        with self.factory() as db:
            result["locations"] = {
                key or "UNKNOWN": value
                for key, value in db.execute(
                    select(
                        YoutubeContentModel.storage_location,
                        func.count(YoutubeContentModel.id),
                    )
                    .where(YoutubeContentModel.step != ContentStep.DELETED)
                    .group_by(YoutubeContentModel.storage_location)
                ).all()
            }
            result["transfers"] = {
                key: value
                for key, value in db.execute(
                    select(
                        StorageTransferModel.status, func.count(StorageTransferModel.id)
                    ).group_by(StorageTransferModel.status)
                ).all()
            }
            result["queued_bytes"] = db.scalar(
                select(
                    func.coalesce(
                        func.sum(
                            StorageTransferModel.total_bytes
                            - StorageTransferModel.bytes_transferred
                        ),
                        0,
                    )
                ).where(
                    StorageTransferModel.status.in_(["PENDING", "RUNNING", "ERROR"])
                )
            )
        return result

    def listing(
        self,
        page: int,
        limit: int,
        status: str | None,
        search: str,
        location: str | None = None,
    ) -> dict[str, Any]:
        with self.factory() as db:
            query = (
                select(StorageTransferModel, YoutubeContentModel, DriveBackupModel)
                .options(inventory_columns())
                .join(
                    YoutubeContentModel,
                    YoutubeContentModel.id == StorageTransferModel.content_id,
                )
                .outerjoin(
                    DriveBackupModel,
                    DriveBackupModel.content_id == YoutubeContentModel.id,
                )
            )
            if status:
                query = query.where(StorageTransferModel.status == status)
            if location:
                query = query.where(YoutubeContentModel.storage_location == location)
            if search:
                query = query.where(
                    or_(
                        YoutubeContentModel.title.ilike(f"%{search}%"),
                        YoutubeContentModel.external_id == search,
                    )
                )
            total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = db.execute(
                query.order_by(
                    StorageTransferModel.updated_at.desc(),
                    StorageTransferModel.id.desc(),
                )
                .offset((page - 1) * limit)
                .limit(limit)
            ).all()
            items = []
            for transfer, content, backup in rows:
                items.append(
                    {
                        "id": transfer.id,
                        "external_id": content.external_id,
                        "title": content.title,
                        "origin": content.origin,
                        "storage_location": content.storage_location,
                        "operation": transfer.operation,
                        "status": transfer.status,
                        "bytes_transferred": transfer.bytes_transferred,
                        "total_bytes": transfer.total_bytes,
                        "attempts": transfer.attempts,
                        "error": transfer.error,
                        "next_retry_at": transfer.next_retry_at,
                        "updated_at": transfer.updated_at,
                        "file_path": content.file_path,
                        "drive_url": (
                            backup.web_url if backup and backup.verified else None
                        ),
                    }
                )
            return {"items": items, "total": total, "page": page, "limit": limit}

    def history(
        self, external_id: str, page: int = 1, limit: int = 50
    ) -> dict[str, Any]:
        with self.factory() as db:
            content_id = db.scalar(
                select(YoutubeContentModel.id).where(
                    YoutubeContentModel.external_id == external_id
                )
            )
            if content_id is None:
                raise ValueError("Content not found.")
            query = select(StorageEventModel).where(
                StorageEventModel.content_id == content_id
            )
            total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
            items = db.scalars(
                query.order_by(StorageEventModel.id.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            ).all()
            return {
                "items": [
                    {
                        key: getattr(item, key)
                        for key in (
                            "id",
                            "action",
                            "details",
                            "previous_location",
                            "new_location",
                            "created_at",
                        )
                    }
                    for item in items
                ],
                "total": total,
                "page": page,
                "limit": limit,
            }
