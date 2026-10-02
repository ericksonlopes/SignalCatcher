import json
import re
from typing import Any
from urllib.parse import urlparse

UF_CODES = set(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)


def positive(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Boolean is not an identity.")
    if not re.fullmatch(r"[1-9][0-9]*", str(value)):
        raise ValueError("Identity must be a positive integer.")
    result = int(value)
    if result <= 0:
        raise ValueError("Identity must be positive.")
    return result


def identity(uri: str, resource: str) -> int:
    parsed = urlparse(uri)
    match = re.fullmatch(rf"/api/v2/{resource}/([1-9][0-9]*)/?", parsed.path)
    if parsed.scheme != "https" or parsed.netloc != "dadosabertos.camara.leg.br" or not match:
        raise ValueError("Invalid source identity URI.")
    return int(match.group(1))


def properties(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
        for key, value in row.items()
        if value is not None
    }
