from pathlib import Path

from src.core.config.settings import settings
from src.modules.youtube.application.use_cases.jobs.storage_manager import (
    StorageManager,
)
from src.modules.youtube.infrastructure.repositories.storage_repository import (
    StorageRepository,
)
from src.modules.youtube.infrastructure.services.drive_storage import DriveStorage
from src.modules.youtube.infrastructure.services.storage_files import StorageFiles


def drive_backup_job() -> None:
    repository = StorageRepository()
    drive = None
    if Path(settings.GOOGLE_DRIVE_OAUTH_PATH).is_file():
        try:
            drive = DriveStorage(settings.GOOGLE_DRIVE_OAUTH_PATH, settings.GOOGLE_DRIVE_FOLDER_ID)
        except Exception as exc:
            repository.record_health({}, str(exc)[:2000])
    StorageManager(repository, StorageFiles(settings.DOWNLOAD_YOUTUBE_PATH), drive).run()
