from typing import TYPE_CHECKING

from src.modules.demograph.domain.contracts import Run
from src.modules.demograph.infrastructure.extraction.selection import people

if TYPE_CHECKING:
    from src.modules.demograph.infrastructure.extraction.transport import ChamberTransport


def extract(source: "ChamberTransport", run: Run, dataset: str) -> None:
    ids = people(source, run)
    for index, person_id in enumerate(sorted(ids)):
        source.paged(
            run,
            dataset,
            f"deputados/{person_id}/historico",
            str(person_id),
            {"person_id": person_id},
            pagination=False,
        )
        source.catalog.progress(run.id, resources_done=index + 1, resources_total=len(ids))
