import csv
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def safe_path(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes storage root.")
    return target


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows(path: Path, metadata: dict[str, Any]) -> Iterator[dict[str, Any]]:
    if path.suffix == ".csv":
        with path.open(encoding=metadata.get("encoding", "utf-8-sig"), newline="") as handle:
            yield from csv.DictReader(handle, delimiter=";")
    else:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        data = envelope.get("dados", envelope) if isinstance(envelope, dict) else envelope
        if isinstance(data, dict):
            yield data
        elif isinstance(data, list):
            for row in data:
                if not isinstance(row, dict):
                    raise ValueError("Source contains a non-object record.")
                yield row
        else:
            raise ValueError("Invalid source envelope.")
