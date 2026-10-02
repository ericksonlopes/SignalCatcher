from datetime import date
from typing import TYPE_CHECKING

from src.modules.demograph.domain.contracts import Run
from src.modules.demograph.infrastructure.extraction.transport import FILES

if TYPE_CHECKING:
    from src.modules.demograph.infrastructure.extraction.transport import ChamberTransport


def extract_annual(source: "ChamberTransport", run: Run, dataset: str) -> None:
    kind = "votacoes" if dataset == "votings" else "votacoesVotos"
    for year in range(
        date.fromisoformat(run.parameters["start"]).year,
        date.fromisoformat(run.parameters["end"]).year + 1,
    ):
        source.fetch(
            run,
            dataset,
            f"{kind}-{year}.csv",
            f"{FILES}{kind}/csv/{kind}-{year}.csv",
            {"year": year},
        )
