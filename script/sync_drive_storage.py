"""Run inventory or a bounded Drive transfer pass without starting the scheduler."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory media and process Google Drive copies.")
    parser.add_argument("--path", help="Override DOWNLOAD_YOUTUBE_PATH for this run.")
    parser.add_argument(
        "--inventory-only", action="store_true", help="Update inventory; no uploads."
    )
    args = parser.parse_args()
    from src.core.config.settings import settings
    from src.modules.youtube.application.use_cases.jobs.storage_manager import (
        StorageManager,
    )
    from src.modules.youtube.infrastructure.repositories.storage_repository import (
        StorageRepository,
    )
    from src.modules.youtube.infrastructure.services.drive_storage import DriveStorage
    from src.modules.youtube.infrastructure.services.storage_files import StorageFiles

    drive = None
    if not args.inventory_only and Path(settings.GOOGLE_DRIVE_OAUTH_PATH).is_file():
        drive = DriveStorage(settings.GOOGLE_DRIVE_OAUTH_PATH, settings.GOOGLE_DRIVE_FOLDER_ID)
    repository = StorageRepository()
    manager = StorageManager(
        repository, StorageFiles(args.path or settings.DOWNLOAD_YOUTUBE_PATH), drive
    )
    if args.inventory_only:
        manager.reconcile(None)
    else:
        manager.run()
    summary = repository.summary()
    print("Locations:", summary["locations"])
    print("Transfers:", summary["transfers"])
    print("Drive authorized:", summary["drive_ready"])


if __name__ == "__main__":
    main()
