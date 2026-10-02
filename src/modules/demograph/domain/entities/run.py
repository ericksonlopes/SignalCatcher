from dataclasses import dataclass, field
from typing import Any


@dataclass
class Run:
    id: str
    operation: str
    extraction_id: str
    parameters: dict[str, Any]
    status: str = "queued"
    stage: str = "queued"
    progress: dict[str, Any] = field(default_factory=dict)
    completed_stages: list[str] = field(default_factory=list)
    cancel_requested: bool = False
