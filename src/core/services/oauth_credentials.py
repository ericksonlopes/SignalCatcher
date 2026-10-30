"""Atomically persist private OAuth credentials without logging their contents."""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any


class OAuthAccessLogFilter(logging.Filter):
    """Never persist browser authorization codes in Uvicorn's access log."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            path = record.args[2]
            if isinstance(path, str) and "/drive-oauth/callback?" in path:
                record.args = (
                    *record.args[:2],
                    path.split("?", 1)[0],
                    *record.args[3:],
                )
        return True


def write_oauth_credentials(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**payload, "type": "authorized_user"}
    descriptor, temporary_name = tempfile.mkstemp(prefix=".oauth-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump(payload, destination)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
