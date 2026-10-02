from typing import TYPE_CHECKING

from src.modules.demograph.domain.contracts import Run
from src.modules.demograph.infrastructure.extraction.selection import voting_ids
from src.modules.demograph.infrastructure.extraction.transport import API
from src.modules.demograph.infrastructure.storage.files import rows, safe_path

if TYPE_CHECKING:
    from src.modules.demograph.infrastructure.extraction.transport import ChamberTransport


def extract(source: "ChamberTransport", run: Run, dataset: str) -> None:
    propositions: set[int] = set()
    selected_votings = voting_ids(source, run)
    for index, voting_id in enumerate(sorted(selected_votings)):
        artifact = source.fetch(
            run,
            dataset,
            f"voting-{voting_id}.json",
            f"{API}votacoes/{voting_id}",
            {"kind": "voting_detail", "voting_id": voting_id},
        )
        detail = list(rows(safe_path(source.root, artifact["path"]), artifact["metadata_json"]))
        if len(detail) != 1 or str(detail[0].get("id")) != voting_id:
            raise ValueError("Voting detail does not match its requested identity.")
        for field in ("objetosPossiveis", "proposicoesAfetadas"):
            for proposition in detail[0].get(field, []):
                propositions.add(int(proposition["id"]))
        source.catalog.progress(
            run.id, resources_done=index + 1, resources_total=len(selected_votings)
        )
    for proposition_id in sorted(propositions):
        source.paged(
            run,
            dataset,
            f"proposicoes/{proposition_id}/temas",
            f"proposition-{proposition_id}",
            {"kind": "proposition_topics", "proposition_id": proposition_id},
            allow_missing=True,
            pagination=False,
        )
