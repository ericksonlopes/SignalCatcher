from typing import TYPE_CHECKING

from src.modules.demograph.domain.contracts import Run
from src.modules.demograph.infrastructure.storage.files import rows, safe_path

if TYPE_CHECKING:
    from src.modules.demograph.infrastructure.extraction.transport import ChamberTransport


def voting_ids(source: "ChamberTransport", run: Run) -> set[str]:
    result = set()
    for artifact in source.catalog.artifacts(run.extraction_id, "votings"):
        for index, row in enumerate(
            rows(safe_path(source.root, artifact["path"]), artifact["metadata_json"])
        ):
            if index % 1000 == 0:
                source.guard(run.id)
            if run.parameters["start"] <= row["data"] <= run.parameters["end"]:
                result.add(str(row["id"]))
    return result


def people(source: "ChamberTransport", run: Run) -> set[int]:
    result: set[int] = set()
    for artifact in source.catalog.artifacts(run.extraction_id, "deputies"):
        for row in rows(safe_path(source.root, artifact["path"]), artifact["metadata_json"]):
            result.add(int(row["id"]))
    selected_votings = voting_ids(source, run)
    for artifact in source.catalog.artifacts(run.extraction_id, "votes"):
        for index, row in enumerate(
            rows(safe_path(source.root, artifact["path"]), artifact["metadata_json"])
        ):
            if index % 1000 == 0:
                source.guard(run.id)
            if row["idVotacao"] in selected_votings:
                result.add(int(row["deputado_id"]))
    return result
