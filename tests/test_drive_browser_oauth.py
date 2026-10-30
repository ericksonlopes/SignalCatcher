import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.config.settings import settings
from src.core.services.oauth_credentials import write_oauth_credentials
from src.modules.youtube.infrastructure.repositories.models.storage_model import (
    DriveOAuthSessionModel,
)
from src.modules.youtube.presentation.api.routes import drive_oauth_route


class BrowserOAuthTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.callback = "http://127.0.0.1:8000/api/youtube/drive-oauth/callback"
        client = root / "client.json"
        client.write_text(
            json.dumps(
                {
                    "web": {
                        "client_id": "test-client.apps.googleusercontent.com",
                        "client_secret": "test-only",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.callback],
                    }
                }
            ),
            encoding="utf-8",
        )
        for key, value in (
            ("GOOGLE_DRIVE_CLIENT_JSON_PATH", str(client)),
            ("GOOGLE_DRIVE_OAUTH_PATH", str(root / "token.json")),
            ("GOOGLE_DRIVE_OAUTH_REDIRECT_URI", self.callback),
        ):
            change = patch.object(settings, key, value)
            change.start()
            self.addCleanup(change.stop)
        self.engine = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        self.addCleanup(self.engine.dispose)
        DriveOAuthSessionModel.__table__.create(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        change = patch.object(drive_oauth_route, "Session", self.factory)
        change.start()
        self.addCleanup(change.stop)
        app = FastAPI()
        app.include_router(drive_oauth_route.router, prefix="/api/youtube")
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def start(self):
        response = self.client.get(
            "/api/youtube/drive-oauth/connect", follow_redirects=False
        )
        self.assertEqual(response.status_code, 303)
        parameters = parse_qs(urlparse(response.headers["location"]).query)
        self.assertEqual(parameters["code_challenge_method"], ["S256"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        return parameters["state"][0]

    def test_status_does_not_expose_client_secret(self):
        response = self.client.get("/api/youtube/drive-oauth/status")
        self.assertTrue(response.json()["configured"])
        self.assertNotIn("test-only", response.text)
        self.assertNotIn("client_secret", response.text)

    def test_callback_rejects_state_without_browser_cookie(self):
        state = self.start()
        self.client.cookies.clear()
        response = self.client.get(
            "/api/youtube/drive-oauth/callback",
            params={"state": state, "code": "unused"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Path(settings.GOOGLE_DRIVE_OAUTH_PATH).exists())

    def test_cancelled_consent_consumes_session(self):
        state = self.start()
        response = self.client.get(
            "/api/youtube/drive-oauth/callback",
            params={"state": state, "error": "access_denied"},
        )
        self.assertEqual(response.status_code, 400)
        with self.factory() as db:
            self.assertEqual(
                db.scalar(select(func.count()).select_from(DriveOAuthSessionModel)), 0
            )
        response = self.client.get(
            "/api/youtube/drive-oauth/callback",
            params={"state": state, "code": "unused"},
            headers={"Cookie": f"{drive_oauth_route.COOKIE}={state}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_expired_state_is_rejected(self):
        state = self.start()
        with self.factory.begin() as db:
            session = db.get(
                DriveOAuthSessionModel, hashlib.sha256(state.encode()).hexdigest()
            )
            session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        response = self.client.get(
            "/api/youtube/drive-oauth/callback",
            params={"state": state, "code": "unused"},
        )
        self.assertEqual(response.status_code, 400)

    def test_private_remote_http_callback_is_not_accepted(self):
        with patch.object(
            settings,
            "GOOGLE_DRIVE_OAUTH_REDIRECT_URI",
            "http://eriberry.local/callback",
        ):
            self.assertFalse(
                self.client.get("/api/youtube/drive-oauth/status").json()["configured"]
            )

    def test_atomic_token_uses_authorized_user_format(self):
        path = Path(settings.GOOGLE_DRIVE_OAUTH_PATH)
        write_oauth_credentials(path, {"refresh_token": "test-only"})
        self.assertEqual(json.loads(path.read_text())["type"], "authorized_user")
        self.assertEqual(list(path.parent.glob(".oauth-*")), [])


if __name__ == "__main__":
    unittest.main()
