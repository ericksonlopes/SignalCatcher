from typing import Protocol

from src.modules.demograph.domain.entities.run import Run


class Analyzer(Protocol):
    def analyze(self, run: Run) -> None: ...
