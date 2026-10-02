import re
from datetime import date
from typing import Any

from src.modules.demograph.domain.mapping.common import properties


def map_record(raw: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {"properties": properties(raw)}
    voting_id = str(raw["id"])
    if not re.fullmatch(r"[0-9]+-[0-9]+", voting_id):
        raise ValueError("Invalid voting identity.")
    date.fromisoformat(raw["data"])
    row.update(id=voting_id, date=raw["data"], description=raw.get("descricao", ""))
    return row
