"""Filesystem operations shared by inventory, upload and restore."""

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Any

from src.core.utils.file_utils import sanitize_path_parts

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".flv",
    ".m4v",
    ".ts",
    ".3gp",
}
VIDEO_ID = re.compile(r"^([A-Za-z0-9_-]{11})(?:_|\.)")
FRAGMENT = re.compile(r"\.(?:f\d+|part\d*|temp)(?:\.|$)", re.IGNORECASE)


class StorageFiles:
    def __init__(self, root: str):
        self.root = Path(root).expanduser().resolve()
        self.sizes: dict[Path, int] = {}

    def confined(self, path: Path) -> Path:
        result = path.resolve()
        if not result.is_relative_to(self.root) or result == self.root:
            raise ValueError("Media path is outside the downloads directory.")
        return result

    def from_public(self, value: str | None) -> Path | None:
        if not value:
            return None
        value = value.replace("\\", "/")
        path = (
            self.root / value.removeprefix("/youtube/")
            if value.startswith("/youtube/")
            else Path(value)
        )
        if not path.is_absolute():
            path = self.root / path
        return self.confined(path)

    def inventory(self) -> dict[str, Path]:
        if not self.root.is_dir():
            raise FileNotFoundError("Downloads directory is unavailable; check the SSD mount.")
        result: dict[str, Path] = {}
        self.sizes = {}
        directories = [self.root]
        while directories:
            with os.scandir(directories.pop()) as entries:
                for entry in entries:
                    meta = entry.stat(follow_symlinks=False)
                    if entry.is_symlink() or (
                        getattr(meta, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                    ):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in {".staging", ".cache"}:
                            directories.append(Path(entry.path))
                        continue
                    path = Path(entry.path)
                    if path.suffix.lower() not in VIDEO_EXTENSIONS or FRAGMENT.search(entry.name):
                        continue
                    match = VIDEO_ID.match(entry.name)
                    if match and entry.is_file(follow_symlinks=False) and meta.st_size > 0:
                        result.setdefault(match[1], path)
                        self.sizes[path] = meta.st_size
        return result

    def locate(self, item: dict[str, Any], inventory: dict[str, Path]) -> Path | None:
        # The inventory already checked these entries and their metadata via scandir.
        # Prefer it to thousands of additional resolve/stat round trips over SMB.
        indexed = inventory.get(str(item["external_id"]))
        if indexed is not None:
            return indexed
        for value in (item.get("file_path"), item.get("staging_path")):
            path = self.from_public(value)
            if path and path.is_file() and path.stat().st_size:
                return path
        return None

    def size(self, path: Path) -> int:
        return self.sizes[path] if path in self.sizes else path.stat().st_size

    def relative(self, path: Path) -> str:
        if not path.is_relative_to(self.root):
            path = self.confined(path)
        return path.relative_to(self.root).as_posix()

    def public(self, path: Path) -> str:
        return "/youtube/" + self.relative(path)

    def destination(self, item: dict[str, Any], relative: str | None = None) -> Path:
        if relative:
            return self.confined(self.root / relative)
        return self.confined(
            self.root.joinpath(
                *sanitize_path_parts(str(item.get("origin") or "")),
                f"{item['external_id']}.mp4",
            )
        )

    @staticmethod
    def checksum(path: Path) -> str:
        digest = hashlib.md5(usedforsecurity=False)
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
