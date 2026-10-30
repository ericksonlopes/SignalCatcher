"""Browser OAuth: HttpOnly state binding, PKCE, expiry and one-time callbacks."""

import hashlib
import html
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy import delete

from src.core.config.settings import settings
from src.core.database.connector import Session
from src.core.database.job_control import JobControlRepository
from src.core.services.oauth_credentials import write_oauth_credentials
from src.modules.youtube.infrastructure.repositories.models.storage_model import (
    DriveOAuthSessionModel,
)
from src.modules.youtube.infrastructure.repositories.storage_repository import (
    StorageRepository,
)
from src.modules.youtube.infrastructure.services.drive_storage import DriveStorage

router = APIRouter(prefix="/drive-oauth")
COOKIE = "signalcatcher_drive_oauth"
SCOPES = ["https://www.googleapis.com/auth/drive"]


def client_configuration() -> dict:
    path = Path(settings.GOOGLE_DRIVE_CLIENT_JSON_PATH)
    if not path.is_file():
        raise ValueError("missing_client")
    with path.open(encoding="utf-8") as source:
        configuration = json.load(source)
    if "web" not in configuration:
        raise ValueError("web_client_required")
    uri = settings.GOOGLE_DRIVE_OAUTH_REDIRECT_URI
    parsed = urlparse(uri)
    if (
        (
            parsed.scheme != "https"
            and not (
                parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            )
        )
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid_redirect_uri")
    if uri not in configuration["web"].get("redirect_uris", []):
        raise ValueError("redirect_uri_not_registered")
    return configuration


@router.get("/status")
def oauth_status():
    parsed = urlparse(settings.GOOGLE_DRIVE_OAUTH_REDIRECT_URI)
    configured, reason = True, None
    try:
        client_configuration()
    except (OSError, ValueError, KeyError):
        configured, reason = False, "client_setup_required"
    return {
        "configured": configured,
        "reason": reason,
        "redirect_uri": settings.GOOGLE_DRIVE_OAUTH_REDIRECT_URI,
        "connect_url": (
            f"{parsed.scheme}://{parsed.netloc}/api/youtube/drive-oauth/connect"
            if configured
            else None
        ),
        "authorized": Path(settings.GOOGLE_DRIVE_OAUTH_PATH).is_file(),
    }


@router.get("/connect")
def connect_drive():
    try:
        configuration = client_configuration()
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(
            503, "Configure the Google Web OAuth client and callback URL first."
        ) from exc
    state = secrets.token_urlsafe(32)
    flow = Flow.from_client_config(
        configuration,
        SCOPES,
        redirect_uri=settings.GOOGLE_DRIVE_OAUTH_REDIRECT_URI,
        autogenerate_code_verifier=True,
    )
    authorization_url, _ = flow.authorization_url(
        state=state, access_type="offline", prompt="consent"
    )
    with Session.begin() as db:
        db.execute(
            delete(DriveOAuthSessionModel).where(
                DriveOAuthSessionModel.expires_at < datetime.now(timezone.utc)
            )
        )
        db.add(
            DriveOAuthSessionModel(
                state_hash=hashlib.sha256(state.encode()).hexdigest(),
                code_verifier=flow.code_verifier,
                redirect_uri=settings.GOOGLE_DRIVE_OAUTH_REDIRECT_URI,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
        )
    response = RedirectResponse(authorization_url, status_code=303)
    response.set_cookie(
        COOKIE,
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=settings.GOOGLE_DRIVE_OAUTH_REDIRECT_URI.startswith("https://"),
        path="/api/youtube/drive-oauth",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def callback_page(message: str, success: bool) -> HTMLResponse:
    response = HTMLResponse(
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>SignalCatcher · Google Drive</title>"
        '<body style="background:#09090b;color:#e4e4e7;font:16px system-ui;padding:48px">'
        f"<h1>Google Drive</h1><p>{html.escape(message)}</p>"
        "<p>Volte à tela Tracking do SignalCatcher.</p></body></html>",
        status_code=200 if success else 400,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )
    response.delete_cookie(COOKIE, path="/api/youtube/drive-oauth")
    return response


@router.get("/callback", response_class=HTMLResponse)
def drive_callback(request: Request, state: str = "", code: str = "", error: str = ""):
    cookie = request.cookies.get(COOKIE, "")
    if not state or not cookie or not secrets.compare_digest(state, cookie):
        return callback_page("Sessão de autorização inválida. Inicie a conexão novamente.", False)
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    with Session.begin() as db:
        session = db.get(DriveOAuthSessionModel, state_hash, with_for_update=True)
        if session is None:
            return callback_page("Autorização já utilizada ou expirada. Inicie novamente.", False)
        expires = session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        verifier, redirect_uri = session.code_verifier, session.redirect_uri
        db.delete(session)
    if expires <= datetime.now(timezone.utc) or error or not code:
        return callback_page("A autorização expirou ou foi cancelada no Google.", False)
    try:
        flow = Flow.from_client_config(
            client_configuration(),
            SCOPES,
            code_verifier=verifier,
            redirect_uri=redirect_uri,
        )
        flow.fetch_token(code=code)
        if not flow.credentials.refresh_token:
            return callback_page("O Google não concedeu acesso offline. Autorize novamente.", False)
        payload = json.loads(flow.credentials.to_json())
        path = Path(settings.GOOGLE_DRIVE_OAUTH_PATH)
        # Validate the account/destination before replacing an existing authorization.
        candidate = path.with_name(".candidate-" + secrets.token_hex(16) + ".json")
        try:
            write_oauth_credentials(candidate, payload)
            info = DriveStorage(str(candidate), settings.GOOGLE_DRIVE_FOLDER_ID).inspect()
            write_oauth_credentials(path, payload)
        finally:
            candidate.unlink(missing_ok=True)
        StorageRepository().record_health(info)
        with Session.begin() as db:
            JobControlRepository(db).request("youtube_drive_backup")
    except Exception:
        # OAuth responses and exceptions may contain authorization codes; never echo them.
        return callback_page(
            "Não foi possível concluir a conexão. Confira a conta e o acesso à pasta.",
            False,
        )
    return callback_page("Conta conectada. As cópias serão processadas pelo servidor.", True)
