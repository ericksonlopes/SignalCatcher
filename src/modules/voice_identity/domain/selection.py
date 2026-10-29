"""Pure selection and identity rules; preview never schedules processing."""

import hashlib
import json
import math
from typing import Any


def validate_selection(start: float, end: float, duration: float) -> None:
    if not all(math.isfinite(v) for v in (start, end, duration)):
        raise ValueError("Selection times must be finite")
    if not 0 <= start < end <= duration:
        raise ValueError("Selection must satisfy 0 <= start < end <= duration")


def transcript_version(result: dict[str, Any] | None, revision: str | None = None) -> str:
    content = {k: (result or {}).get(k) for k in ("segments", "duration", "language")}
    content["revision"] = revision
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def selection_key(person_id: str, task_id: str, version: str, start: float, end: float) -> str:
    return hashlib.sha256(
        json.dumps([person_id, task_id, version, start, end]).encode()
    ).hexdigest()
