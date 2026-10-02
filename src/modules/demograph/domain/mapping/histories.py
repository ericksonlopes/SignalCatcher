import hashlib
import json
from datetime import datetime
from typing import Any

from src.modules.demograph.domain.mapping.common import positive, properties


def map_record(raw: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {"properties": properties(raw)}
    datetime.fromisoformat(raw["dataHora"])
    row.update(person_id=positive(metadata["person_id"]), at=raw["dataHora"])
    row["key"] = hashlib.sha256(
        json.dumps([row["person_id"], raw], sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return row
