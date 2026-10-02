from datetime import datetime
from typing import Any

from src.modules.demograph.domain.mapping.common import identity, positive, properties


def map_record(raw: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {"properties": properties(raw)}
    choice = str(raw["voto"]).strip()
    if not choice:
        raise ValueError("Missing vote choice.")
    datetime.fromisoformat(raw["dataHoraVoto"])
    row.update(
        id=positive(raw["deputado_id"]),
        voting_id=str(raw["idVotacao"]),
        choice=choice,
        name=raw["deputado_nome"],
        at=raw["dataHoraVoto"],
        party_id=identity(raw["deputado_uriPartido"], "partidos")
        if raw.get("deputado_uriPartido")
        else None,
    )
    if identity(raw["deputado_uri"], "deputados") != row["id"]:
        raise ValueError("Vote person identity mismatch.")
    return row
