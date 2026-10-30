import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from src.modules.youtube.application.use_cases.jobs.storage_manager import (
    StorageManager,
)
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.storage import TransferInterrupted
from src.modules.youtube.infrastructure.repositories.models.step_tracking_model import (
    StepTrackingModel,
)
from src.modules.youtube.infrastructure.repositories.models.storage_model import (
    DriveBackupModel,
    StorageEventModel,
    StorageSettingsModel,
    StorageTransferModel,
)
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)
from src.modules.youtube.infrastructure.repositories.storage_repository import (
    StorageRepository,
)
from src.modules.youtube.infrastructure.services.storage_files import StorageFiles


class MemoryDrive:
    def __init__(self):
        self.files = {}
        self.payloads = {}
        self.uploads = 0
        self.catalog_entries = []

    def inspect(self):
        return {"free_bytes": 1000000}

    def managed_files(self):
        return list(self.files.values())

    def reserve_id(self):
        return f"remote-{len(self.files) + 1}"

    def get_file(self, file_id):
        return self.files.get(file_id)

    def upload(self, path, relative_path, external_id, file_id, session_uri, progress):
        payload = path.read_bytes()
        progress(0, len(payload), "https://www.googleapis.com/upload/test-session")
        self.files[file_id] = {
            "id": file_id,
            "size": str(len(payload)),
            "md5Checksum": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
            "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
        }
        self.payloads[file_id] = payload
        self.uploads += 1
        progress(len(payload), len(payload), session_uri)
        return self.files[file_id]

    def download(self, file_id, path, progress):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.payloads[file_id])
        progress(path.stat().st_size, path.stat().st_size, None)

    def save_catalog(self, entries):
        self.catalog_entries = entries


class YoutubeStorageTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.engine = create_engine("sqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        self.factory = sessionmaker(bind=self.engine, autoflush=False)
        for model in (
            YoutubeContentModel,
            StepTrackingModel,
            StorageSettingsModel,
            DriveBackupModel,
            StorageTransferModel,
            StorageEventModel,
        ):
            model.__table__.create(self.engine)
        self.repository = StorageRepository(self.factory)
        self.files = StorageFiles(self.directory.name)
        self.drive = MemoryDrive()
        self.manager = StorageManager(self.repository, self.files, self.drive)

    def content(self, staging=False):
        relative = "channel/12345678901_title.mp4"
        path = Path(self.directory.name) / (".staging/" + relative if staging else relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"complete video bytes")
        with self.factory() as db, db.begin():
            item = YoutubeContentModel(
                external_id="12345678901",
                title="Title",
                origin="channel",
                url="https://youtube.com/watch?v=12345678901",
                step=ContentStep.DOWNLOADED if staging else ContentStep.COMPLETED,
                file_path=None if staging else "/youtube/" + relative,
                staging_path="/youtube/.staging/" + relative if staging else None,
                storage_mode="DRIVE" if staging else "BOTH",
            )
            db.add(item)
        return path

    def test_upload_verified_copy_and_repeat_does_not_duplicate(self):
        path = self.content()
        self.manager.run()
        self.manager.run()
        self.assertTrue(path.is_file())
        self.assertEqual(self.drive.uploads, 1)
        with self.factory() as db:
            item = db.scalar(select(YoutubeContentModel))
            self.assertEqual(item.storage_location, "BOTH")
            self.assertEqual(item.drive_file_id, "remote-1")
            self.assertEqual(db.scalar(select(func.count()).select_from(StorageTransferModel)), 1)
            events = db.scalars(select(StorageEventModel.action)).all()
            self.assertIn("UPLOAD_COMPLETED", events)

    def test_drive_only_cleans_only_staging_after_verified_copy(self):
        path = self.content(staging=True)
        self.manager.run()
        self.assertFalse(path.exists())
        with self.factory() as db:
            item = db.scalar(select(YoutubeContentModel))
            self.assertEqual(item.storage_location, "DRIVE")
            self.assertEqual(item.step, ContentStep.COMPLETED)
            self.assertIsNone(item.file_path)
            self.assertIsNone(item.staging_path)

    def test_paused_queue_survives_and_resumes(self):
        self.content()
        self.repository.update_settings({"uploads_paused": True})
        self.manager.run()
        self.assertEqual(self.drive.uploads, 0)
        self.repository.update_settings({"uploads_paused": False})
        self.manager.run()
        self.assertEqual(self.drive.uploads, 1)

    def test_cleanup_permission_failure_preserves_verified_copy_and_retries(self):
        path = self.content(staging=True)
        original_unlink = Path.unlink

        def blocked_unlink(candidate, *args, **kwargs):
            if candidate == path.resolve():
                raise PermissionError("temporary file is read-only")
            return original_unlink(candidate, *args, **kwargs)

        with patch.object(Path, "unlink", blocked_unlink):
            self.manager.run()
        self.assertTrue(path.exists())
        with self.factory() as db:
            self.assertEqual(db.scalar(select(StorageTransferModel.status)), "COMPLETED")
            self.assertEqual(db.scalar(select(YoutubeContentModel.storage_location)), "DRIVE")
        self.manager.run()
        self.assertFalse(path.exists())
        self.assertEqual(self.drive.uploads, 1)

    def test_restore_keeps_remote_and_updates_both(self):
        path = self.content(staging=True)
        self.manager.run()
        with self.factory() as db:
            content_id = db.scalar(select(YoutubeContentModel.id))
        self.repository.enqueue(content_id, "RESTORE", "BOTH")
        self.manager.run()
        restored = Path(self.directory.name, "channel/12345678901_title.mp4")
        self.assertEqual(restored.read_bytes(), b"complete video bytes")
        self.assertFalse(path.exists())
        self.assertEqual(len(self.drive.files), 1)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(YoutubeContentModel.storage_location)), "BOTH")

    def test_wrong_checksum_keeps_local_and_does_not_confirm_remote(self):
        path = self.content()
        upload = self.drive.upload

        def corrupt(*args):
            result = upload(*args)
            return {**result, "md5Checksum": "bad-checksum"}

        self.drive.upload = corrupt
        self.manager.run()
        self.assertTrue(path.exists())
        with self.factory() as db:
            self.assertEqual(db.scalar(select(StorageTransferModel.status)), "ERROR")
            self.assertEqual(db.scalar(select(YoutubeContentModel.storage_location)), "LOCAL")

    def test_replaced_lease_cannot_overwrite_new_owner(self):
        self.content()
        self.manager.reconcile([])
        task = self.repository.claim()
        self.assertIsNotNone(task)
        with self.factory() as db, db.begin():
            transfer = db.get(StorageTransferModel, task["task_id"])
            transfer.lease_token = "another-worker"
        with self.assertRaises(TransferInterrupted):
            self.repository.finish(task, {})


if __name__ == "__main__":
    unittest.main()
