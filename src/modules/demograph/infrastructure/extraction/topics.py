from typing import TYPE_CHECKING

from src.modules.demograph.domain.contracts import Run
from src.modules.demograph.infrastructure.extraction.parallel import resources
from src.modules.demograph.infrastructure.extraction.selection import voting_ids
from src.modules.demograph.infrastructure.extraction.transport import API
from src.modules.demograph.infrastructure.storage.files import rows, safe_path

if TYPE_CHECKING:
    from src.modules.demograph.infrastructure.extraction.transport import ChamberTransport


def extract(source: "ChamberTransport", run: Run, dataset: str) -> None:
    propositions: set[int] = set()
    selected_votings = voting_ids(source, run)

    def voting_detail(transport: "ChamberTransport", voting_id: str) -> set[int]:
        artifact = transport.fetch(
            run,
            dataset,
            f"voting-{voting_id}.json",
            f"{API}votacoes/{voting_id}",
            {"kind": "voting_detail", "voting_id": voting_id},
        )
        detail = list(rows(safe_path(source.root, artifact["path"]), artifact["metadata_json"]))
        if len(detail) != 1 or str(detail[0].get("id")) != voting_id:
            raise ValueError("Voting detail does not match its requested identity.")
        identities: set[int] = set()
        for field in ("objetosPossiveis", "proposicoesAfetadas"):
            for proposition in detail[0].get(field, []):
                identities.add(int(proposition["id"]))
        return identities

    source.progress(
        run.id,
        resources_done=0,
        resources_total=len(selected_votings),
        resources_phase="voting_details",
    )
    for index, identities in enumerate(
        resources(source, run.id, sorted(selected_votings), voting_detail)
    ):
        propositions.update(identities)
        source.progress(run.id, resources_done=index + 1, resources_total=len(selected_votings))

    def proposition_topics(transport: "ChamberTransport", proposition_id: int) -> None:
        transport.paged(
            run,
            dataset,
            f"proposicoes/{proposition_id}/temas",
            f"proposition-{proposition_id}",
            {"kind": "proposition_topics", "proposition_id": proposition_id},
            allow_missing=True,
            pagination=False,
        )

    source.progress(
        run.id,
        resources_done=0,
        resources_total=len(propositions),
        resources_phase="proposition_topics",
    )
    for index, _ in enumerate(resources(source, run.id, sorted(propositions), proposition_topics)):
        source.progress(run.id, resources_done=index + 1)
