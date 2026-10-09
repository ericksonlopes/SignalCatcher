import secrets
from typing import Annotated

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

admin_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_admin(
    request: Request, api_key: Annotated[str | None, Security(admin_key_header)]
) -> None:
    pass


def require_metrics_admin(api_key: Annotated[str | None, Security(admin_key_header)]) -> None:
    pass
