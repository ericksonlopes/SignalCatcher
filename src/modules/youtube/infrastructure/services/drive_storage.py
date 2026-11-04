"""Private Google Drive binary transfers with durable resumable sessions."""

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as UserCredentials

from src.modules.youtube.domain.storage import ProgressCallback, StorageBlocked

API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
FIELDS = "id,name,size,md5Checksum,webViewLink,trashed"
CHUNK = 8 * 1024 * 1024


class DriveStorage:
    def __init__(self, credentials_path: str, folder_id: str):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", folder_id):
            raise ValueError("Invalid Google Drive destination folder ID.")
        credential_file = Path(credentials_path)
        if not credential_file.is_file():
            raise StorageBlocked("Google Drive credential file is missing.")
        try:
            with credential_file.open(encoding="utf-8") as source:
                payload = json.load(source)
            if not isinstance(payload, dict):
                raise ValueError("Google Drive credentials must be a JSON object.")
            kind = payload.get("type")
            self._service_account = kind == "service_account"
            scopes = ["https://www.googleapis.com/auth/drive"]
            credentials: service_account.Credentials | UserCredentials
            if self._service_account:
                credentials = service_account.Credentials.from_service_account_file(
                    str(credential_file), scopes=scopes
                )
            elif kind == "authorized_user":
                credentials = UserCredentials.from_authorized_user_file(
                    str(credential_file), scopes=scopes
                )
            else:
                raise ValueError("Unsupported Google Drive credential type.")
        except (OSError, ValueError) as exc:
            raise StorageBlocked(
                "Google Drive credentials are invalid or unreadable. "
                "Use a service-account key or an authorized-user token."
            ) from exc
        self.session = AuthorizedSession(credentials, refresh_timeout=30)
        self.folder_id = folder_id
        self.drive_id: str | None = None
        self.folders: dict[str, str] = {"": folder_id}

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        # Shared-drive files require these flags on metadata, media and upload requests.
        if not urlparse(url).query and (
            url == f"{API}/files"
            or (url.startswith(f"{API}/files/") and url != f"{API}/files/generateIds")
            or url == UPLOAD
            or url.startswith(f"{UPLOAD}/")
        ):
            params = dict(kwargs.get("params", {}))
            params["supportsAllDrives"] = "true"
            if method == "GET" and url == f"{API}/files":
                params["includeItemsFromAllDrives"] = "true"
            kwargs["params"] = params
        response = self.session.request(method, url, timeout=(10, 90), **kwargs)
        if response.status_code in {200, 201, 204, 206, 308, 404}:
            return response
        try:
            message = response.json().get("error", {}).get("message", "Google Drive request failed")
        except ValueError:
            message = "Google Drive request failed"
        # Never expose request/session URLs or credentials in API errors or logs.
        if response.status_code in {401, 403}:
            raise StorageBlocked(f"Google Drive {response.status_code}: {message}")
        raise RuntimeError(f"Google Drive {response.status_code}: {message}")

    def inspect(self) -> dict[str, Any]:
        response = self._request(
            "GET",
            f"{API}/files/{self.folder_id}",
            params={
                "fields": "id,name,mimeType,trashed,driveId,capabilities(canAddChildren)",
                "supportsAllDrives": "true",
            },
        )
        if response.status_code == 404:
            raise StorageBlocked("The configured Google Drive folder is not accessible.")
        folder = response.json()
        if not folder.get("driveId") and self._service_account:
            raise StorageBlocked(
                "Service-account uploads require a folder in a Google Workspace shared drive. "
                "A shared My Drive folder does not provide storage quota."
            )
        if (
            folder.get("mimeType") != "application/vnd.google-apps.folder"
            or folder.get("trashed")
            or not folder.get("capabilities", {}).get("canAddChildren")
        ):
            raise StorageBlocked("The destination folder does not allow file creation.")
        about = self._request(
            "GET", f"{API}/about", params={"fields": "user(emailAddress),storageQuota"}
        ).json()
        self.drive_id = folder.get("driveId")
        return {
            "folder_id": self.folder_id,
            "folder_name": folder["name"],
            "folder_url": f"https://drive.google.com/drive/folders/{self.folder_id}",
            "account": about.get("user", {}).get("emailAddress"),
            "shared_drive_id": self.drive_id,
            **self._storage_quota(about),
        }

    def _storage_quota(self, about: dict[str, Any]) -> dict[str, int | None]:
        # Personal quota is only relevant to an authorized user's My Drive destination.
        if self.drive_id:
            return {"limit_bytes": None, "used_bytes": None, "free_bytes": None}
        quota = about.get("storageQuota", {})
        limit = int(quota["limit"]) if quota.get("limit") else None
        used = int(quota["usage"]) if quota.get("usage") is not None else None
        free = max(0, limit - used) if limit is not None and used is not None else None
        return {"limit_bytes": limit, "used_bytes": used, "free_bytes": free}

    def reserve_id(self) -> str:
        return self._request(
            "GET",
            f"{API}/files/generateIds",
            params={"count": 1, "space": "drive", "type": "files"},
        ).json()["ids"][0]

    def get_file(self, file_id: str) -> dict[str, Any] | None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
            raise ValueError("Invalid Google Drive file ID.")
        response = self._request("GET", f"{API}/files/{file_id}", params={"fields": FIELDS})
        if response.status_code == 404:
            return None
        result = response.json()
        return None if result.get("trashed") else result

    def _list(self, query: str, fields: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        token = None
        while True:
            params = {
                "q": query,
                "fields": f"files({fields}),nextPageToken",
                "pageSize": 1000,
            }
            if self.drive_id:
                params.update({"corpora": "drive", "driveId": self.drive_id})
            if token:
                params["pageToken"] = token
            data = self._request("GET", f"{API}/files", params=params).json()
            result.extend(data.get("files", []))
            token = data.get("nextPageToken")
            if not token:
                return result

    def managed_files(self) -> list[dict[str, Any]]:
        return self._list(
            "trashed=false and appProperties has {key='signalcatcher_root' "
            f"and value='{self.folder_id}'}}",
            FIELDS,
        )

    def _folder(self, relative: str) -> str:
        if relative in self.folders:
            return self.folders[relative]
        path = PurePosixPath(relative)
        parent = self._folder(str(path.parent) if str(path.parent) != "." else "")
        name = path.name.replace("\\", "\\\\").replace("'", "\\'")
        existing = self._list(
            f"'{parent}' in parents and trashed=false and "
            f"mimeType='application/vnd.google-apps.folder' and name='{name}'",
            "id",
        )
        if len(existing) > 1:
            raise StorageBlocked(f"Duplicate destination channel folders: {relative}")
        if existing:
            folder_id = existing[0]["id"]
        else:
            folder_id = self._request(
                "POST",
                f"{API}/files",
                json={
                    "name": path.name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent],
                },
                params={"fields": "id"},
            ).json()["id"]
        self.folders[relative] = folder_id
        return folder_id

    def upload(
        self,
        path: Path,
        relative_path: str,
        external_id: str,
        file_id: str,
        session_uri: str | None,
        progress: ProgressCallback,
    ) -> dict[str, Any]:
        total = path.stat().st_size
        remote = self.get_file(file_id)
        offset = 0
        if session_uri:
            response = self._probe_upload(session_uri, total)
            if response.status_code in {200, 201}:
                return self.get_file(file_id) or response.json()
            if response.status_code == 404:
                session_uri = None
            else:
                received = response.headers.get("Range")
                offset = int(received.rsplit("-", 1)[-1]) + 1 if received else 0
        if not session_uri:
            session_uri = self._start_upload(
                path, relative_path, external_id, file_id, remote, total
            )
            progress(0, total, session_uri)
        return self._upload_chunks(path, file_id, session_uri, offset, total, progress)

    def _probe_upload(self, session_uri: str, total: int) -> Any:
        parsed = urlparse(session_uri)
        if parsed.scheme != "https" or parsed.hostname != "www.googleapis.com":
            raise ValueError("Invalid persisted upload session host.")
        return self._request(
            "PUT",
            session_uri,
            headers={"Content-Range": f"bytes */{total}", "Content-Length": "0"},
            data=b"",
        )

    def _start_upload(
        self,
        path: Path,
        relative_path: str,
        external_id: str,
        file_id: str,
        remote: dict[str, Any] | None,
        total: int,
    ) -> str:
        parent_path = str(PurePosixPath(relative_path).parent)
        parent = self._folder("" if parent_path == "." else parent_path)
        metadata: dict[str, Any] = {
            "name": path.name,
            "appProperties": {
                "signalcatcher_root": self.folder_id,
                "youtube_id": external_id,
            },
        }
        if remote is None:
            metadata.update({"id": file_id, "parents": [parent]})
        response = self._request(
            "PATCH" if remote else "POST",
            f"{UPLOAD}/{file_id}" if remote else UPLOAD,
            params={"uploadType": "resumable", "fields": FIELDS},
            json=metadata,
            headers={
                "X-Upload-Content-Type": "application/octet-stream",
                "X-Upload-Content-Length": str(total),
            },
        )
        return response.headers["Location"]

    def _upload_chunks(
        self,
        path: Path,
        file_id: str,
        session_uri: str,
        offset: int,
        total: int,
        progress: ProgressCallback,
    ) -> dict[str, Any]:
        with path.open("rb") as source:
            source.seek(offset)
            while offset < total:
                progress(offset, total, session_uri)
                data = source.read(CHUNK)
                if not data:
                    raise RuntimeError("The source file changed during upload.")
                response = self._request(
                    "PUT",
                    session_uri,
                    data=data,
                    headers={
                        "Content-Length": str(len(data)),
                        "Content-Range": f"bytes {offset}-{offset + len(data) - 1}/{total}",
                    },
                )
                if response.status_code == 404:
                    raise RuntimeError("Upload session expired; the next attempt will restart it.")
                if response.status_code in {200, 201}:
                    progress(total, total, session_uri)
                    return self.get_file(file_id) or response.json()
                received = response.headers.get("Range")
                if not received:
                    raise RuntimeError("Google did not acknowledge uploaded bytes.")
                offset = int(received.rsplit("-", 1)[-1]) + 1
                source.seek(offset)
        raise RuntimeError("Google did not confirm the completed upload.")

    def download(self, file_id: str, path: Path, progress: ProgressCallback) -> None:
        info = self.get_file(file_id)
        if not info:
            raise FileNotFoundError("The remote video is missing or in the trash.")
        total = int(info["size"])
        path.parent.mkdir(parents=True, exist_ok=True)
        offset = path.stat().st_size if path.exists() else 0
        if offset == total:
            progress(offset, total, None)
            return
        if offset > total:
            offset = 0
        progress(offset, total, None)
        response = self._request(
            "GET",
            f"{API}/files/{file_id}",
            params={"alt": "media"},
            headers={"Range": f"bytes={offset}-"} if offset else {},
            stream=True,
        )
        if response.status_code == 404:
            raise FileNotFoundError("The remote video is missing.")
        if response.status_code == 200:
            offset = 0
        try:
            with path.open("ab" if offset else "wb") as target:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        target.write(chunk)
                        offset += len(chunk)
                        progress(offset, total, None)
        finally:
            response.close()
        if offset != total:
            raise RuntimeError("Incomplete Drive download; retry will resume it.")

    def save_catalog(self, entries: list[dict[str, Any]]) -> None:
        existing = self._list(
            f"'{self.folder_id}' in parents and trashed=false and "
            "appProperties has {key='signalcatcher_catalog' and value='1'}",
            "id",
        )
        if len(existing) > 1:
            raise StorageBlocked("Multiple managed catalogs found in the destination.")
        if existing:
            file_id = existing[0]["id"]
        else:
            file_id = self._request(
                "POST",
                f"{API}/files",
                params={"fields": "id"},
                json={
                    "name": "catalog.json",
                    "mimeType": "application/json",
                    "parents": [self.folder_id],
                    "appProperties": {"signalcatcher_catalog": "1"},
                },
            ).json()["id"]
        data = json.dumps({"version": 1, "videos": entries}, ensure_ascii=False).encode("utf-8")
        self._request(
            "PATCH",
            f"{UPLOAD}/{file_id}",
            params={"uploadType": "media"},
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
