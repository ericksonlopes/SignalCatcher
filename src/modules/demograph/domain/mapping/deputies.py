from typing import Any

from src.modules.demograph.domain.mapping.common import UF_CODES, identity, positive, properties


def map_record(raw: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {"properties": properties(raw)}
    row.update(
        id=positive(raw["id"]),
        name=str(raw["nome"]).strip(),
        state=str(raw["siglaUf"]).upper(),
        legislature=positive(raw["idLegislatura"]),
        party_id=identity(raw["uriPartido"], "partidos") if raw.get("uriPartido") else None,
        party_name=raw.get("siglaPartido"),
    )
    if (
        identity(raw["uri"], "deputados") != row["id"]
        or row["state"] not in UF_CODES
        or not row["name"]
    ):
        raise ValueError("Invalid deputy identity, name or state.")
    return row
