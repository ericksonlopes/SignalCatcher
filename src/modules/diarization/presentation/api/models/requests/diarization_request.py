from pydantic import BaseModel


class DiarizationRequest(BaseModel):
    language: str | None = "en"
    start_now: bool = False
