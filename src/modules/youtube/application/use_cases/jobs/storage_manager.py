"""Orchestrates durable transfers without holding database transactions over I/O."""

from pathlib import Path
from time import monotonic, sleep
from typing import Any

from src.modules.youtube.domain.storage import (
    IDriveStorage,
    IStorageFiles,
    IStorageRepository,
    ProgressCallback,
    StorageBlocked,
    TransferInterrupted,
)

STAGING_PREFIX = ".staging/"


class _TransferProgress:
    def __init__(self, repository: IStorageRepository, task: dict[str, Any]):
        self.repository = repository
        self.task = task
        self.started = monotonic()
        self.initial_sent: int | None = None
        self.last_checkpoint = 0.0

    def __call__(self, sent: int, total: int, session_uri: str | None) -> None:
        if self.initial_sent is None:
            self.initial_sent = sent
        # Upload chunks always checkpoint; restore streams checkpoint every second.
        if session_uri is not None or monotonic() - self.last_checkpoint >= 1 or sent == total:
            self.repository.checkpoint(self.task, sent, total, session_uri)
            self.last_checkpoint = monotonic()
        if self.task["operation"] == "UPLOAD":
            self._throttle(sent, total, session_uri)

    def _throttle(self, sent: int, total: int, session_uri: str | None) -> None:
        limit = self.repository.settings()["max_upload_mib_per_second"]
        if not limit:
            return
        assert self.initial_sent is not None
        duration = (sent - self.initial_sent) / (limit * 1024 * 1024)
        remaining = duration - (monotonic() - self.started)
        while remaining > 0:
            sleep(min(1, remaining))
            self.repository.checkpoint(self.task, sent, total, session_uri)
            remaining = duration - (monotonic() - self.started)


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
        remote_by_id = (
            {item["id"]: item for item in remote_files} if remote_files is not None else None
        )
        observations = [
            self._observation(item, inventory, remote_by_id)
            for item in self.repository.candidates()
        ]
        self.repository.reconcile(observations, self.repository.settings()["mode"])

    def _observation(
        self,
        item: dict[str, Any],
        inventory: dict[str, Path],
        remote_by_id: dict[str, dict[str, Any]] | None,
    ) -> dict[str, Any]:
        remote = None
        if remote_by_id is not None:
            remote_id = item.get("drive_file_id")
            metadata = remote_by_id.get(remote_id) if remote_id is not None else None
            remote = self._copy_matches(
                metadata,
                item.get("drive_md5"),
                item.get("drive_size"),
            )
        path = self.files.locate(item, inventory)
        path = self._reconcile_staging(item, path, remote)
        relative = self.files.relative(path) if path else None
        staging = bool(relative and relative.startswith(STAGING_PREFIX))
        return {
            "id": item["id"],
            "source": str(path) if path else None,
            "relative": relative.removeprefix(STAGING_PREFIX) if relative else None,
            "local": self.files.public(path) if path and not staging else None,
            "size": self.files.size(path) if path else None,
            "remote": remote,
            "eligible": item["step"] in {"COMPLETED", "DOWNLOADED"},
        }

    def _reconcile_staging(
        self, item: dict[str, Any], path: Path | None, remote: bool | None
    ) -> Path | None:
        if not path or not remote:
            return path
        if not self.files.relative(path).startswith(STAGING_PREFIX):
            return path
        if self.files.size(path) != item.get("drive_size"):
            return path
        if self.files.checksum(path) != item.get("drive_md5"):
            return path
        self.cleanup_staging(item["id"], path)
        return path if path.exists() else None

    @staticmethod
    def _copy_matches(
        remote: dict[str, Any] | None, checksum: str | None, size: int | None
    ) -> bool:
        return bool(
            remote and remote.get("md5Checksum") == checksum and int(remote.get("size", -1)) == size
        )

    def run(self, max_seconds: int = 240) -> None:
        info, remote_files = self._inspect_drive()
        self.reconcile(remote_files)
        if not self.drive or not self.repository.settings()["drive_ready"]:
            return
        self._process_queue(info, monotonic() + max_seconds)
        self._save_catalog()

    def _inspect_drive(self) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
        info: dict[str, Any] = {}
        remote_files = None
        try:
            if self.drive is None:
                raise StorageBlocked("Google Drive credentials are not configured on the server.")
            info = self.drive.inspect()
            remote_files = self.drive.managed_files()
            self.repository.record_health(info)
        except Exception as exc:
            self.repository.record_health({}, str(exc)[:2000])
        return info, remote_files

    def _process_queue(self, info: dict[str, Any], deadline: float) -> None:
        while monotonic() < deadline:
            task = self.repository.claim()
            if task is None:
                break
            if not self._process_transfer(task, info):
                break

    def _process_transfer(self, task: dict[str, Any], info: dict[str, Any]) -> bool:
        try:
            self.transfer(task, info)
        except TransferInterrupted:
            self.repository.release(task)
            return not self.repository.settings()["uploads_paused"]
        except StorageBlocked as exc:
            self.repository.fail(task, str(exc), blocked=True)
            return False
        except Exception as exc:
            self.repository.fail(task, str(exc))
        return True

    def _save_catalog(self) -> None:
        assert self.drive is not None
        try:
            entries = self.repository.catalog()
            if entries:
                self.drive.save_catalog(entries)
                self.repository.catalog_result(None)
        except Exception as exc:
            self.repository.catalog_result(str(exc)[:2000])

    def transfer(self, task: dict[str, Any], info: dict[str, Any]) -> None:
        assert self.drive is not None
        progress = _TransferProgress(self.repository, task)
        if task["operation"] == "RESTORE":
            self._restore(task, progress)
        else:
            self._upload(task, info, progress)

    def _restore(self, task: dict[str, Any], progress: ProgressCallback) -> None:
        assert self.drive is not None
        destination = self.files.destination(task, task["relative_path"])
        partial = None
        if destination.is_file():
            if (
                self.files.checksum(destination, lambda: progress(task["size"], task["size"], None))
                != task["md5"]
            ):
                raise ValueError("Restore conflict: a different local file already exists.")
        else:
            partial = self.files.confined(destination.with_name(destination.name + ".restore.part"))
            self.drive.download(task["file_id"], partial, progress)
            if (
                self.files.checksum(partial, lambda: progress(task["size"], task["size"], None))
                != task["md5"]
            ):
                partial.unlink(missing_ok=True)
                raise ValueError("Restore checksum mismatch; the partial file was discarded.")

        def publish() -> None:
            if partial is not None:
                # Hard-link creation refuses to overwrite a file created concurrently.
                destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    destination.hardlink_to(partial)
                except FileExistsError:
                    raise ValueError(
                        "Restore conflict: destination appeared during transfer."
                    ) from None

        self.repository.finish(task, {"file_path": self.files.public(destination)}, publish)
        if partial is not None:
            partial.unlink(missing_ok=True)

    def _upload(
        self, task: dict[str, Any], info: dict[str, Any], progress: ProgressCallback
    ) -> None:
        path = self.files.locate(task, {})
        if path is None:
            raise FileNotFoundError(f"Missing source: {task['external_id']}")
        before = path.stat()
        checksum = self.files.checksum(
            path,
            lambda: self.repository.checkpoint(
                task, task["bytes_transferred"], before.st_size, task["session_uri"]
            ),
        )
        result = self._upload_copy(task, info, path, before.st_size, checksum, progress)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Source changed during upload; the copy was not confirmed.")
        if not self._copy_matches(result, checksum, before.st_size):
            raise ValueError("Google Drive copy failed size/checksum verification.")
        self.repository.finish(task, result)
        # Only temporary downloads are eligible for cleanup. Existing local media is preserved.
        if self.files.relative(path).startswith(STAGING_PREFIX):
            self.cleanup_staging(task["content_id"], path)

    def _upload_copy(
        self,
        task: dict[str, Any],
        info: dict[str, Any],
        path: Path,
        size: int,
        checksum: str,
        progress: ProgressCallback,
    ) -> dict[str, Any]:
        assert self.drive is not None
        file_id = task["file_id"]
        if not file_id:
            file_id = self.drive.reserve_id()
            self.repository.reserve_remote(task, file_id)
        remote = self.drive.get_file(file_id)
        if self._copy_matches(remote, checksum, size):
            assert remote is not None
            return remote
        free = info.get("free_bytes")
        if free is not None and free < size:
            raise StorageBlocked("Insufficient space in Google Drive for the next video.")
        result = self.drive.upload(
            path, task["relative_path"], task["external_id"], file_id, task["session_uri"], progress
        )
        if free is not None:
            info["free_bytes"] = max(0, free - size)
        return result

    def cleanup_staging(self, content_id: int, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            self.repository.staging_cleanup_failed(content_id, str(exc))
        else:
            self.repository.staging_removed(content_id)
