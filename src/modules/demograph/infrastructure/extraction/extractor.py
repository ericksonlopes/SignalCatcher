from src.modules.demograph.domain.contracts import Run
from src.modules.demograph.infrastructure.extraction import (
    deputies,
    histories,
    topics,
    votes,
    votings,
)
from src.modules.demograph.infrastructure.extraction.selection import people, voting_ids
from src.modules.demograph.infrastructure.extraction.transport import ChamberTransport

EXTRACTORS = {
    "deputies": deputies.extract,
    "votings": votings.extract,
    "votes": votes.extract,
    "histories": histories.extract,
    "topics": topics.extract,
}


class ChamberExtractor(ChamberTransport):
    def extract(self, run: Run) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for dataset in run.parameters["datasets"]:
            stage = f"extract:{dataset}"
            if stage in self.catalog.run(run.id).completed_stages:
                continue
            self.guard(run.id)
            self.catalog.update(run.id, stage=stage)
            EXTRACTORS[dataset](self, run, dataset)
            current = self.catalog.run(run.id)
            self.catalog.update(run.id, completed_stages=[*current.completed_stages, stage])
        self.catalog.progress(run.id, extraction_complete=True)

    def voting_ids(self, run: Run) -> set[str]:
        return voting_ids(self, run)

    def people(self, run: Run) -> set[int]:
        return people(self, run)
