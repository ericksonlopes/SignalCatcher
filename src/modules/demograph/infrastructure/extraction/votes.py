from typing import TYPE_CHECKING

from src.modules.demograph.domain.contracts import Run
from src.modules.demograph.infrastructure.extraction.annual import extract_annual

if TYPE_CHECKING:
    from src.modules.demograph.infrastructure.extraction.transport import ChamberTransport


def extract(source: "ChamberTransport", run: Run, dataset: str) -> None:
    extract_annual(source, run, dataset)
