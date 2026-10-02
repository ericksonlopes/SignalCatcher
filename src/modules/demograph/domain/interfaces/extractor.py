from typing import Protocol

from src.modules.demograph.domain.entities.run import Run


class Extractor(Protocol):
    def extract(self, run: Run) -> None: ...
