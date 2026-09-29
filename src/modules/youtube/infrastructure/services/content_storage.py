import re
from pathlib import Path

from src.core.utils.file_utils import sanitize_path_parts
from src.modules.youtube.domain.entities.youtube_content_entity import YoutubeContentEntity


class ContentStorage:
    def __init__(self, output_path: str):
        self.root = Path(output_path).resolve()

    def _confined(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root) or resolved == self.root:
            raise ValueError("Content path is outside the downloads directory.")
        return resolved

    def delete_files(self, content: YoutubeContentEntity) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", content.external_id):
            raise ValueError("Invalid content identifier for file removal.")
        directory = self._confined(self.root.joinpath(*sanitize_path_parts(content.origin)))
        candidates = set(directory.glob(f"{content.external_id}_*"))
        if content.file_path:
            # Stored paths are public /youtube/... paths, not host paths.
            if not content.file_path.startswith("/youtube/"):
                raise ValueError("Invalid stored content path.")
            candidates.add(self.root / content.file_path.removeprefix("/youtube/"))
        resolved_candidates = []
        for candidate in candidates:
            if not candidate.name.startswith(f"{content.external_id}_") or candidate.is_symlink():
                raise ValueError("Content removal only accepts files owned by this video.")
            resolved_candidates.append(self._confined(candidate))
        for candidate in resolved_candidates:
            if candidate.exists() and not candidate.is_file():
                raise ValueError("Content removal only accepts files.")
        for candidate in resolved_candidates:
            candidate.unlink(missing_ok=True)
