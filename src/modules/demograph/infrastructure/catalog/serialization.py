from datetime import datetime, timezone
from typing import Any


def now() -> datetime:
    return datetime.now(timezone.utc)


def model_dict(model: Any) -> dict[str, Any]:
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}
