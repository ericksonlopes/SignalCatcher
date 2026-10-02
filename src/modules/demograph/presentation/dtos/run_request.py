from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.modules.demograph.domain.contracts import resolve_datasets


class RunRequest(BaseModel):
    operation: Literal["extract", "pipeline"] = "pipeline"
    datasets: list[str] = Field(min_length=1, max_length=5)
    start: date
    end: date

    @model_validator(mode="after")
    def validate_selection(self) -> "RunRequest":
        resolve_datasets(self.datasets)
        if self.start > self.end or self.end > date.today():
            raise ValueError("The period must be ordered and cannot end in the future.")
        return self
