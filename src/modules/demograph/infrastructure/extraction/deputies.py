from typing import TYPE_CHECKING

from src.modules.demograph.domain.contracts import Run

if TYPE_CHECKING:
    from src.modules.demograph.infrastructure.extraction.transport import ChamberTransport


def extract(source: "ChamberTransport", run: Run, dataset: str) -> None:
    source.paged(run, dataset, "deputados", "current", {})
