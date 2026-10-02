from typing import Any, Protocol

from src.modules.demograph.domain.entities.run import Run


class Loader(Protocol):
    def load(self, run: Run) -> None: ...
    def schema(self, run_id: str | None = None) -> dict[str, Any]: ...
