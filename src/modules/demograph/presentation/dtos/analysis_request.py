from datetime import date

from pydantic import BaseModel, Field, model_validator


class AnalysisRequest(BaseModel):
    start: date
    end: date
    min_party_votes: int = Field(default=1, ge=1, le=1000)
    min_common: int = Field(default=30, ge=1, le=100000)

    @model_validator(mode="after")
    def validate_period(self) -> "AnalysisRequest":
        if self.start > self.end or self.end > date.today():
            raise ValueError("The period must be ordered and cannot end in the future.")
        return self
