import secrets
from typing import Annotated

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from src.core.config.settings import settings

admin_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_admin(
    request: Request, api_key: Annotated[str | None, Security(admin_key_header)]
) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    expected = settings.ADMIN_API_KEY
    if expected is None or not expected.get_secret_value():
        raise HTTPException(503, "Administrative access is not configured.")
    if api_key is None or not secrets.compare_digest(
        api_key.encode(), expected.get_secret_value().encode()
    ):
        raise HTTPException(401, "Invalid administrative API key.")


def require_metrics_admin(api_key: Annotated[str | None, Security(admin_key_header)]) -> None:
    expected = settings.ADMIN_API_KEY
    if expected is None or not expected.get_secret_value():
        raise HTTPException(503, "Administrative access is not configured.")
    if api_key is None or not secrets.compare_digest(
        api_key.encode(), expected.get_secret_value().encode()
    ):
        raise HTTPException(401, "Invalid administrative API key.")
