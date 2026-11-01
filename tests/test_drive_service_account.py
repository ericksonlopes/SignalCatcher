import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch
from unittest.mock import call as mock_call

from src.modules.youtube.domain.storage import StorageBlocked
from src.modules.youtube.infrastructure.services import drive_storage


def response(status=200, payload=None, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = payload or {}
    return result


class ServiceAccountDriveTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.key = Path(directory.name, "service_account.json")
        self.key.write_text("{}", encoding="utf-8")
        self.video = self.key.with_name("video.mp4")
        self.video.write_bytes(b"video bytes")
        credentials = patch.object(
            drive_storage.service_account.Credentials, "from_service_account_file"
        )
        self.credentials = credentials.start()
        self.addCleanup(credentials.stop)
        session = patch.object(drive_storage, "AuthorizedSession")
        self.session_factory = session.start()
        self.addCleanup(session.stop)
        self.session = self.session_factory.return_value
        self.drive = drive_storage.DriveStorage(str(self.key), "destination")

    def test_uses_existing_service_account_with_write_scope(self):
        self.credentials.assert_called_once_with(
            str(self.key), scopes=["https://www.googleapis.com/auth/drive"]
        )
        self.session_factory.assert_called_once_with(
            self.credentials.return_value, refresh_timeout=30
        )

    def test_missing_or_invalid_key_reports_configuration_error_without_secrets(self):
        missing_key = str(self.key.with_name("missing.json"))
        with self.assertRaisesRegex(StorageBlocked, "credential file is missing"):
            drive_storage.DriveStorage(missing_key, "destination")
        self.credentials.side_effect = ValueError("private-key-content")
        key_path = str(self.key)
        with self.assertRaises(StorageBlocked) as error:
            drive_storage.DriveStorage(key_path, "destination")
        self.assertNotIn("private-key-content", str(error.exception))

    def test_inaccessible_folder_is_not_reported_as_ready(self):
        self.session.request.return_value = response(404)
        with self.assertRaisesRegex(StorageBlocked, "not accessible"):
            self.drive.inspect()

    def test_personal_folder_with_editor_permission_is_not_reported_as_upload_ready(self):
        self.session.request.return_value = response(
            payload={
                "id": "destination",
                "name": "Videos",
                "mimeType": "application/vnd.google-apps.folder",
                "capabilities": {"canAddChildren": True},
            }
        )
        with self.assertRaisesRegex(StorageBlocked, "Workspace shared drive"):
            self.drive.inspect()
        self.assertEqual(self.session.request.call_count, 1)

    def test_shared_folder_is_ready_without_using_service_accounts_personal_quota(self):
        self.session.request.side_effect = [
            response(
                payload={
                    "id": "destination",
                    "name": "Videos",
                    "driveId": "shared-drive",
                    "mimeType": "application/vnd.google-apps.folder",
                    "capabilities": {"canAddChildren": True},
                }
            ),
            response(payload={"user": {"emailAddress": "worker@example.invalid"}}),
        ]
        info = self.drive.inspect()
        self.assertEqual(info["shared_drive_id"], "shared-drive")
        self.assertEqual(info["account"], "worker@example.invalid")
        self.assertIsNone(info["free_bytes"])
        self.assertIsNone(info["used_bytes"])
        self.assertEqual(
            self.session.request.call_args_list[0].kwargs["params"]["supportsAllDrives"], "true"
        )

    def test_inventory_includes_shared_drive_items_across_pages(self):
        self.session.request.side_effect = [
            response(payload={"files": [{"id": "one"}], "nextPageToken": "next"}),
            response(payload={"files": [{"id": "two"}]}),
        ]
        self.assertEqual([item["id"] for item in self.drive.managed_files()], ["one", "two"])
        for call in self.session.request.call_args_list:
            self.assertEqual(call.kwargs["params"]["includeItemsFromAllDrives"], "true")
            self.assertEqual(call.kwargs["params"]["supportsAllDrives"], "true")
        self.assertEqual(self.session.request.call_args.kwargs["params"]["pageToken"], "next")

    def test_resumable_upload_supports_shared_drive_without_changing_session_url(self):
        path = self.key.with_name("video.mp4")
        path.write_bytes(b"video bytes")
        session_uri = f"{drive_storage.UPLOAD}/video-id?uploadType=resumable&upload_id=test"
        self.session.request.side_effect = [
            response(404),
            response(headers={"Location": session_uri}),
            response(payload={"id": "video-id"}),
            response(payload={"id": "video-id", "size": "11"}),
        ]
        result = self.drive.upload(path, "video.mp4", "youtube-id", "video-id", None, Mock())
        self.assertEqual(result["id"], "video-id")
        create = self.session.request.call_args_list[1]
        self.assertEqual(create.kwargs["params"]["supportsAllDrives"], "true")
        self.assertEqual(create.kwargs["json"]["parents"], ["destination"])
        upload = self.session.request.call_args_list[2]
        self.assertEqual(upload.args, ("PUT", session_uri))
        self.assertNotIn("params", upload.kwargs)

    def test_catalog_create_and_update_support_shared_drives(self):
        self.session.request.side_effect = [
            response(payload={"files": []}),
            response(payload={"id": "catalog-id"}),
            response(),
        ]
        self.drive.save_catalog([{"external_id": "youtube-id"}])
        for call in self.session.request.call_args_list:
            self.assertEqual(call.kwargs["params"]["supportsAllDrives"], "true")
        self.assertEqual(self.session.request.call_args.args[0], "PATCH")

    def test_resume_sends_only_bytes_not_acknowledged_by_google(self):
        session_uri = f"{drive_storage.UPLOAD}?upload_id=existing"
        self.session.request.side_effect = [
            response(404),
            response(308, headers={"Range": "bytes=0-4"}),
            response(payload={"id": "video-id"}),
            response(payload={"id": "video-id", "size": "11"}),
        ]
        progress = Mock()
        result = self.drive.upload(
            self.video, "video.mp4", "youtube-id", "video-id", session_uri, progress
        )
        self.assertEqual(result["id"], "video-id")
        probe = self.session.request.call_args_list[1]
        self.assertEqual(probe.kwargs["headers"]["Content-Range"], "bytes */11")
        chunk = self.session.request.call_args_list[2]
        self.assertEqual(chunk.kwargs["data"], b" bytes")
        self.assertEqual(chunk.kwargs["headers"]["Content-Range"], "bytes 5-10/11")
        progress.assert_any_call(5, 11, session_uri)
        progress.assert_called_with(11, 11, session_uri)

    def test_completed_session_is_confirmed_without_sending_video_again(self):
        session_uri = f"{drive_storage.UPLOAD}?upload_id=completed"
        metadata = {"id": "video-id", "size": "11"}
        self.session.request.side_effect = [
            response(404),
            response(payload=metadata),
            response(payload=metadata),
        ]
        progress = Mock()
        result = self.drive.upload(
            self.video, "video.mp4", "youtube-id", "video-id", session_uri, progress
        )
        self.assertEqual(result, metadata)
        self.assertEqual(self.session.request.call_count, 3)
        progress.assert_not_called()

    def test_expired_session_restarts_upload_from_first_byte(self):
        expired_uri = f"{drive_storage.UPLOAD}?upload_id=expired"
        replacement_uri = f"{drive_storage.UPLOAD}?upload_id=replacement"
        self.session.request.side_effect = [
            response(404),
            response(404),
            response(headers={"Location": replacement_uri}),
            response(payload={"id": "video-id"}),
            response(payload={"id": "video-id"}),
        ]
        self.drive.upload(self.video, "video.mp4", "youtube-id", "video-id", expired_uri, Mock())
        chunk = self.session.request.call_args_list[3]
        self.assertEqual(chunk.args, ("PUT", replacement_uri))
        self.assertEqual(chunk.kwargs["data"], b"video bytes")
        self.assertEqual(chunk.kwargs["headers"]["Content-Range"], "bytes 0-10/11")

    def test_unacknowledged_chunk_is_not_reported_as_completed(self):
        self.session.request.side_effect = [
            response(404),
            response(headers={"Location": f"{drive_storage.UPLOAD}?upload_id=new"}),
            response(308),
        ]
        progress = Mock()
        with self.assertRaisesRegex(RuntimeError, "did not acknowledge"):
            self.drive.upload(self.video, "video.mp4", "youtube-id", "video-id", None, progress)
        self.assertNotIn(mock_call(11, 11, ANY), progress.call_args_list)

    def test_inventory_is_scoped_to_the_destinations_shared_drive(self):
        self.drive.drive_id = "shared-drive"
        self.session.request.return_value = response(payload={"files": []})
        self.drive.managed_files()
        params = self.session.request.call_args.kwargs["params"]
        self.assertEqual(params["corpora"], "drive")
        self.assertEqual(params["driveId"], "shared-drive")


if __name__ == "__main__":
    unittest.main()
