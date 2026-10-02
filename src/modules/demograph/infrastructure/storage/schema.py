import re
from datetime import date, datetime
from typing import Any


def value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def infer_csv_type(text: str) -> str:
    if re.fullmatch(r"-?\d+", text):
        return "integer"
    if re.fullmatch(r"-?\d+\.\d+", text):
        return "number"
    if text.lower() in {"true", "false"}:
        return "boolean"
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            date.fromisoformat(text)
            return "date"
        if re.match(r"\d{4}-\d{2}-\d{2}T", text):
            datetime.fromisoformat(text)
            return "datetime"
    except ValueError:
        pass
    return "string"


class SchemaObserver:
    def __init__(self, csv_mode: bool = False) -> None:
        self.csv_mode = csv_mode
        self.count = 0
        self.fields: dict[str, dict[str, Any]] = {}

    def observe(self, row: dict[str, Any]) -> None:
        self.count += 1
        self._walk(row, "")

    def _walk(self, row: dict[str, Any], prefix: str) -> None:
        for key, value in row.items():
            path = f"{prefix}.{key}" if prefix else key
            field = self.fields.setdefault(
                path,
                {
                    "path": path,
                    "types": [],
                    "present": 0,
                    "nulls": 0,
                    "examples": [],
                    "inferred_types": [],
                },
            )
            field["present"] += 1
            field["nulls"] += value is None or (self.csv_mode and value == "")
            kind = value_type(value)
            if kind not in field["types"]:
                field["types"].append(kind)
            if self.csv_mode and value not in (None, ""):
                text = str(value)
                inferred = infer_csv_type(text)
                if inferred not in field["inferred_types"]:
                    field["inferred_types"].append(inferred)
            if not isinstance(value, (dict, list)) and value is not None:
                example = str(value)[:160]
                if example not in field["examples"] and len(field["examples"]) < 3:
                    field["examples"].append(example)
            if isinstance(value, dict):
                self._walk(value, path)
            if isinstance(value, list):
                # Array entries have a different denominator from root records.
                for entry in value:
                    if isinstance(entry, dict):
                        self._walk(entry, path + "[]")

    def result(self) -> dict[str, Any]:
        return {
            "records": self.count,
            "fields": list(self.fields.values()),
            "presence_unit": "occurrences; array children count array entries",
        }
