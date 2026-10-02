import shutil
from pathlib import Path
from typing import Any
from uuid import UUID

from src.modules.demograph.infrastructure.storage.files import safe_path


class ExtractionFiles:
    def __init__(self, root: Path) -> None:
        self.root = root

    def directory(self, extraction_id: str) -> Path:
        if str(UUID(extraction_id)) != extraction_id:
            raise ValueError("Invalid extraction directory.")
        candidate = self.root / extraction_id
        if candidate.is_symlink():
            raise ValueError("Extraction directory must not be a symbolic link.")
        return safe_path(self.root, extraction_id)

    def validate_deletion(self, extraction_id: str, artifacts: list[dict[str, Any]]) -> None:
        directory = self.directory(extraction_id)
        for artifact in artifacts:
            path = safe_path(self.root, artifact["path"])
            if not path.is_relative_to(directory):
                raise ValueError("Artifact does not belong to the extraction directory.")

    def delete_extraction(self, extraction_id: str) -> None:
        directory = self.directory(extraction_id)
        if directory.exists():
            shutil.rmtree(directory)
