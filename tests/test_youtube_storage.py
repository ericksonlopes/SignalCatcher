import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from src.modules.youtube.application.use_cases.jobs.storage_manager import (
    StorageManager,
)
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.processing import ContentBusyError
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
from src.modules.youtube.infrastructure.repositories.youtube_content_repository import (
    YoutubeContentRepository,
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

    def test_slow_checksum_renews_transfer_and_content_reservations(self):
        self.content()
        clock = datetime.now(timezone.utc)
        checksum = self.files.checksum

        def slow_checksum(path, heartbeat=None):
            nonlocal clock
            for _ in range(3):
                clock += timedelta(seconds=240)
                heartbeat()
                with self.factory() as db:
                    content = db.scalar(select(YoutubeContentModel))
                    transfer = db.scalar(select(StorageTransferModel))
                    self.assertGreater(transfer.lease_expires_at, clock.replace(tzinfo=None))
                    self.assertEqual(content.lease_expires_at, transfer.lease_expires_at)
            return checksum(path)

        with (
            patch(
                "src.modules.youtube.infrastructure.repositories.storage_repository.now",
                side_effect=lambda: clock,
            ),
            patch.object(self.files, "checksum", side_effect=slow_checksum),
        ):
            self.manager.run()
        self.assertEqual(self.drive.uploads, 1)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(StorageTransferModel.status)), "COMPLETED")

    def test_checksum_heartbeats_and_stops_when_reservation_is_lost(self):
        path = self.content()
        path.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        heartbeat = Mock()
        with patch(
            "src.modules.youtube.infrastructure.services.storage_files.monotonic",
            side_effect=[0, 21, 21, 42, 42, 63, 63],
        ):
            actual = self.files.checksum(path, heartbeat)
        self.assertEqual(actual, hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest())
        self.assertEqual(heartbeat.call_count, 3)
        with (
            patch(
                "src.modules.youtube.infrastructure.services.storage_files.monotonic",
                side_effect=[0, 21],
            ),
            self.assertRaises(TransferInterrupted),
        ):
            self.files.checksum(path, Mock(side_effect=TransferInterrupted))

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

    def test_restore_conflict_preserves_existing_local_file_and_remote_copy(self):
        self.content(staging=True)
        self.manager.run()
        with self.factory() as db:
            content_id = db.scalar(select(YoutubeContentModel.id))
        restored = Path(self.directory.name, "channel/12345678901_title.mp4")
        restored.parent.mkdir(parents=True, exist_ok=True)
        restored.write_bytes(b"another local video")
        self.repository.enqueue(content_id, "RESTORE", "BOTH")
        self.manager.run()
        self.assertEqual(restored.read_bytes(), b"another local video")
        self.assertEqual(self.drive.payloads["remote-1"], b"complete video bytes")
        with self.factory() as db:
            transfer = db.scalar(
                select(StorageTransferModel).where(StorageTransferModel.operation == "RESTORE")
            )
            self.assertEqual(transfer.status, "ERROR")
            self.assertIn("Restore conflict", transfer.error)

    def test_unavailable_drive_keeps_local_inventory_and_pending_uploads(self):
        path = self.content()
        self.manager.drive = None
        self.manager.run()
        self.assertTrue(path.exists())
        self.assertEqual(self.drive.uploads, 0)
        self.assertFalse(self.repository.settings()["drive_ready"])
        with self.factory() as db:
            self.assertEqual(db.scalar(select(YoutubeContentModel.storage_location)), "LOCAL")
            self.assertEqual(db.scalar(select(StorageTransferModel.status)), "PENDING")

    def test_inventory_preserves_verified_remote_copy_until_its_loss_is_confirmed(self):
        self.content()
        self.manager.run()
        with self.factory() as db:
            content_id = db.scalar(select(YoutubeContentModel.id))
        for method in ("observe", "reconcile"):
            for local, remote, expected in (
                ("/youtube/channel/12345678901_title.mp4", True, "BOTH"),
                (None, None, "DRIVE"),
                (None, False, "NONE"),
                ("/youtube/channel/12345678901_title.mp4", False, "LOCAL"),
            ):
                with self.subTest(method=method, local=local, remote=remote):
                    if method == "observe":
                        self.repository.observe(content_id, local, remote)
                    else:
                        self.repository.reconcile(
                            [{"id": content_id, "local": local, "remote": remote}], "LOCAL"
                        )
                    with self.factory() as db:
                        item = db.get(YoutubeContentModel, content_id)
                        self.assertEqual(item.storage_location, expected)
                        self.assertEqual(item.file_path, local)
                        self.assertEqual(bool(item.drive_file_id), expected in {"BOTH", "DRIVE"})

    def test_enqueue_does_not_reset_errors_but_requeues_finished_transfers(self):
        self.content()
        with self.factory() as db:
            content_id = db.scalar(select(YoutubeContentModel.id))
        self.repository.enqueue(content_id, "UPLOAD", "BOTH")
        with self.factory() as db, db.begin():
            transfer = db.scalar(select(StorageTransferModel))
            transfer.status = "ERROR"
            transfer.attempts = 3
            transfer.error = "keep-error"
        self.repository.enqueue(content_id, "UPLOAD", "BOTH")
        with self.factory() as db, db.begin():
            transfer = db.scalar(select(StorageTransferModel))
            self.assertEqual(
                (transfer.status, transfer.attempts, transfer.error), ("ERROR", 3, "keep-error")
            )
            transfer.status = "MISSING_FILE"
        self.repository.enqueue(content_id, "UPLOAD", "DRIVE")
        with self.factory() as db:
            transfer = db.scalar(select(StorageTransferModel))
            self.assertEqual(
                (transfer.status, transfer.attempts, transfer.mode), ("PENDING", 0, "DRIVE")
            )
            self.assertIsNone(transfer.error)
            self.assertEqual(db.scalar(select(func.count()).select_from(StorageTransferModel)), 1)
        self.assertEqual(self.repository.summary()["transfers"], {"PENDING": 1})

    def test_upload_rate_limit_keeps_checkpoints_during_throttle(self):
        path = self.content()
        self.repository.update_settings({"max_upload_mib_per_second": 0.1})
        clock = [0.0]

        def advance(seconds):
            clock[0] += seconds

        module = "src.modules.youtube.application.use_cases.jobs.storage_manager"
        with (
            patch(module + ".monotonic", side_effect=lambda: clock[0]),
            patch(module + ".sleep", side_effect=advance) as waiting,
            patch.object(
                self.repository, "checkpoint", wraps=self.repository.checkpoint
            ) as checkpoint,
        ):
            self.manager.run()
        self.assertEqual(self.drive.uploads, 1)
        self.assertGreaterEqual(clock[0], path.stat().st_size / (0.1 * 1024 * 1024))
        waiting.assert_called()
        self.assertGreaterEqual(checkpoint.call_count, 3)

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

    def test_transfer_blocks_deletion_and_reprocessing_until_finished(self):
        self.content()
        self.manager.reconcile([])
        task = self.repository.claim()
        with self.factory() as db:
            repository = YoutubeContentRepository(db, Mock())
            for command in (repository.request_deletion, repository.request_reprocessing):
                with self.assertRaises(ContentBusyError):
                    command(task["external_id"])
        self.manager.transfer(task, {})
        with self.factory() as db, db.begin():
            item = db.get(YoutubeContentModel, task["content_id"])
            self.assertIsNone(item.lease_token)
            self.assertIsNone(item.lease_expires_at)
            self.assertTrue(YoutubeContentRepository(db, Mock()).request_deletion(item.external_id))

    def test_restore_cannot_publish_after_content_reservation_is_revoked(self):
        self.content(staging=True)
        self.manager.run()
        with self.factory() as db:
            content_id = db.scalar(select(YoutubeContentModel.id))
        self.repository.enqueue(content_id, "RESTORE", "BOTH")
        task = self.repository.claim()
        download = self.drive.download

        def revoke_after_download(*args):
            download(*args)
            with self.factory() as db, db.begin():
                item = db.get(YoutubeContentModel, content_id)
                item.step = ContentStep.DELETED
                item.lease_token = item.lease_expires_at = None

        self.drive.download = revoke_after_download
        self.manager._process_transfer(task, {})
        restored = Path(self.directory.name, "channel/12345678901_title.mp4")
        self.assertFalse(restored.exists())
        self.assertIsNone(self.repository.claim())
        with self.factory() as db:
            item = db.get(YoutubeContentModel, content_id)
            self.assertEqual(item.step, ContentStep.DELETED)
            self.assertIsNone(item.file_path)
        with self.assertRaisesRegex(ValueError, "Deleted content"):
            self.repository.enqueue(content_id, "RESTORE", "BOTH")

    def test_transfer_checkpoint_renews_content_reservation_and_release_clears_it(self):
        self.content()
        self.manager.reconcile([])
        task = self.repository.claim()
        self.repository.checkpoint(task, 1, 20, None)
        with self.factory() as db:
            item = db.get(YoutubeContentModel, task["content_id"])
            transfer = db.get(StorageTransferModel, task["task_id"])
            self.assertEqual(item.lease_token, task["token"])
            self.assertEqual(item.lease_expires_at, transfer.lease_expires_at)
        self.repository.release(task)
        with self.factory() as db:
            self.assertIsNone(db.get(YoutubeContentModel, task["content_id"]).lease_token)
        self.assertIsNotNone(self.repository.claim())

    def test_expired_transfer_is_reclaimed_without_releasing_a_new_content_owner(self):
        self.content()
        self.manager.reconcile([])
        task = self.repository.claim()
        expired = datetime.now(timezone.utc) - timedelta(seconds=1)
        with self.factory() as db, db.begin():
            db.get(StorageTransferModel, task["task_id"]).lease_expires_at = expired
            db.get(YoutubeContentModel, task["content_id"]).lease_expires_at = expired
        replacement = self.repository.claim()
        self.assertNotEqual(replacement["token"], task["token"])
        self.repository.release(task)
        with self.factory() as db:
            item = db.get(YoutubeContentModel, task["content_id"])
            self.assertEqual(item.lease_token, replacement["token"])
        with self.factory() as db, db.begin():
            db.get(StorageTransferModel, task["task_id"]).lease_expires_at = expired
            db.get(YoutubeContentModel, task["content_id"]).lease_token = "media-worker"
        self.assertIsNone(self.repository.claim())
        with self.factory() as db:
            self.assertEqual(
                db.get(YoutubeContentModel, task["content_id"]).lease_token, "media-worker"
            )


if __name__ == "__main__":
    unittest.main()
