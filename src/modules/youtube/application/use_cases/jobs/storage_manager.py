"""Orchestrates durable transfers without holding database transactions over I/O."""

from pathlib import Path
from time import monotonic, sleep
from typing import Any

from src.modules.youtube.domain.storage import (
    IDriveStorage,
    IStorageFiles,
    IStorageRepository,
    StorageBlocked,
    TransferInterrupted,
)


class StorageManager:
    def __init__(
        self,
        repository: IStorageRepository,
        files: IStorageFiles,
        drive: IDriveStorage | None,
    ):
        self.repository = repository
        self.files = files
        self.drive = drive

    def reconcile(self, remote_files: list[dict[str, Any]] | None) -> None:
        inventory = self.files.inventory()
        remote_by_id = {item["id"]: item for item in remote_files or []}
        observations = []
        for item in self.repository.candidates():
            path = self.files.locate(item, inventory)
            relative = self.files.relative(path) if path else None
            staging = bool(relative and relative.startswith(".staging/"))
            remote = None
            if remote_files is not None:
                metadata = remote_by_id.get(item.get("drive_file_id"))
                remote = bool(
                    metadata
                    and metadata.get("md5Checksum") == item.get("drive_md5")
                    and int(metadata.get("size", -1)) == item.get("drive_size")
                )
            if (
                remote
                and staging
                and path
                and self.files.size(path) == item.get("drive_size")
            ):
                if self.files.checksum(path) == item.get("drive_md5"):
                    self.cleanup_staging(item["id"], path)
                    if not path.exists():
                        path, relative = None, None
            observations.append(
                {
                    "id": item["id"],
                    "source": str(path) if path else None,
                    "relative": (
                        relative.removeprefix(".staging/") if relative else None
                    ),
                    "local": self.files.public(path) if path and not staging else None,
                    "size": self.files.size(path) if path else None,
                    "remote": remote,
                    "eligible": item["step"] in {"COMPLETED", "DOWNLOADED"},
                }
            )
        self.repository.reconcile(observations, self.repository.settings()["mode"])

    def run(self, max_seconds: int = 240) -> None:
        info: dict[str, Any] = {}
        remote_files = None
        try:
            if self.drive is None:
                raise StorageBlocked(
                    "OAuth authorization is pending. Connect Google Drive in the Tracking screen."
                )
            info = self.drive.inspect()
            remote_files = self.drive.managed_files()
            self.repository.record_health(info)
        except Exception as exc:
            self.repository.record_health({}, str(exc)[:2000])
        self.reconcile(remote_files)
        if not self.drive or not self.repository.settings()["drive_ready"]:
            return
        deadline = monotonic() + max_seconds
        while monotonic() < deadline:
            task = self.repository.claim()
            if task is None:
                break
            try:
                self.transfer(task, info)
            except TransferInterrupted:
                self.repository.release(task)
                if self.repository.settings()["uploads_paused"]:
                    break
            except StorageBlocked as exc:
                self.repository.fail(task, str(exc), blocked=True)
                break
            except Exception as exc:
                self.repository.fail(task, str(exc))
        try:
            entries = self.repository.catalog()
            if entries:
                self.drive.save_catalog(entries)
                self.repository.catalog_result(None)
        except Exception as exc:
            self.repository.catalog_result(str(exc)[:2000])

    def transfer(self, task: dict[str, Any], info: dict[str, Any]) -> None:
        assert self.drive is not None
        started = monotonic()
        initial_sent: int | None = None
        last_checkpoint = 0.0

        def progress(sent: int, total: int, session_uri: str | None) -> None:
            nonlocal initial_sent, last_checkpoint
            if initial_sent is None:
                initial_sent = sent
            # Upload chunks always checkpoint; restore streams checkpoint every second.
            if (
                session_uri is not None
                or monotonic() - last_checkpoint >= 1
                or sent == total
            ):
                self.repository.checkpoint(task, sent, total, session_uri)
                last_checkpoint = monotonic()
            if task["operation"] == "UPLOAD":
                limit = self.repository.settings()["max_upload_mib_per_second"]
                if limit:
                    remaining = (sent - initial_sent) / (limit * 1024 * 1024) - (
                        monotonic() - started
                    )
                    while remaining > 0:
                        sleep(min(1, remaining))
                        self.repository.checkpoint(task, sent, total, session_uri)
                        remaining = (sent - initial_sent) / (limit * 1024 * 1024) - (
                            monotonic() - started
                        )

        if task["operation"] == "RESTORE":
            destination = self.files.destination(task, task["relative_path"])
            if destination.is_file():
                if self.files.checksum(destination) != task["md5"]:
                    raise ValueError(
                        "Restore conflict: a different local file already exists."
                    )
            else:
                partial = self.files.confined(
                    destination.with_name(destination.name + ".restore.part")
                )
                self.drive.download(task["file_id"], partial, progress)
                if self.files.checksum(partial) != task["md5"]:
                    partial.unlink(missing_ok=True)
                    raise ValueError(
                        "Restore checksum mismatch; the partial file was discarded."
                    )
                # Hard-link creation refuses to overwrite a file created concurrently.
                destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    destination.hardlink_to(partial)
                except FileExistsError:
                    if self.files.checksum(destination) != task["md5"]:
                        raise ValueError(
                            "Restore conflict: destination appeared during transfer."
                        ) from None
                partial.unlink(missing_ok=True)
            self.repository.finish(task, {"file_path": self.files.public(destination)})
            return

        path = self.files.locate(task, {})
        if path is None:
            raise FileNotFoundError(f"Missing source: {task['external_id']}")
        before = path.stat()
        checksum = self.files.checksum(path)
        file_id = task["file_id"]
        if not file_id:
            file_id = self.drive.reserve_id()
            self.repository.reserve_remote(task, file_id)
        remote = self.drive.get_file(file_id)
        if (
            remote
            and remote.get("md5Checksum") == checksum
            and int(remote.get("size", -1)) == before.st_size
        ):
            result = remote
        else:
            free = info.get("free_bytes")
            if free is not None and free < before.st_size:
                raise StorageBlocked(
                    "Insufficient space in Google Drive for the next video."
                )
            result = self.drive.upload(
                path,
                task["relative_path"],
                task["external_id"],
                file_id,
                task["session_uri"],
                progress,
            )
            if free is not None:
                info["free_bytes"] = max(0, free - before.st_size)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError(
                "Source changed during upload; the copy was not confirmed."
            )
        if (
            result.get("md5Checksum") != checksum
            or int(result.get("size", -1)) != before.st_size
        ):
            raise ValueError("Google Drive copy failed size/checksum verification.")
        self.repository.finish(task, result)
        # Only temporary downloads are eligible for cleanup. Existing local media is preserved.
        if self.files.relative(path).startswith(".staging/"):
            self.cleanup_staging(task["content_id"], path)

    def cleanup_staging(self, content_id: int, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            self.repository.staging_cleanup_failed(content_id, str(exc))
        else:
            self.repository.staging_removed(content_id)
