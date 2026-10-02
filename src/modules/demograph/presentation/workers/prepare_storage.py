"""Create the shared artifact directory before starting container workers."""

import os
from pathlib import Path

from src.core.config.settings import settings


def prepare_storage() -> Path:
    path = Path(settings.demograph_storage_path)
    path.mkdir(parents=True, exist_ok=True)
    # Docker creates a missing bind-mount directory as root. Transfer only the
    # directory to the application UID, never recursively change existing files.
    if hasattr(os, "geteuid") and os.geteuid() == 0 and path.stat().st_uid == 0:
        getattr(os, "chown")(path, 1000, 1000)
    return path


if __name__ == "__main__":
    prepare_storage()
