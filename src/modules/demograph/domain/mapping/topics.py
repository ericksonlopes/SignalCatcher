from typing import Any

from src.modules.demograph.domain.mapping.common import positive, properties


def map_record(raw: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {"properties": properties(raw)}
    if metadata.get("kind") == "voting_detail":
        row.update(id=str(raw["id"]), possible=[], affected=[])
        if row["id"] != metadata["voting_id"]:
            raise ValueError("Voting detail identity mismatch.")
        for source, target in (
            ("objetosPossiveis", "possible"),
            ("proposicoesAfetadas", "affected"),
        ):
            if not isinstance(raw.get(source), list):
                raise ValueError("Missing proposition links.")
            row[target] = [
                {"id": positive(p["id"]), "properties": properties(p)} for p in raw[source]
            ]
    else:
        row.update(
            proposition_id=positive(metadata["proposition_id"]),
            code=positive(raw["codTema"]),
            name=str(raw["tema"]).strip(),
        )
        if not row["name"]:
            raise ValueError("Missing topic name.")
    return row
