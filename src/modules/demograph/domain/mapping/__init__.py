from typing import Any

from src.modules.demograph.domain.mapping import deputies, histories, topics, votes, votings

MAPPERS = {
    "deputies": deputies.map_record,
    "votings": votings.map_record,
    "votes": votes.map_record,
    "histories": histories.map_record,
    "topics": topics.map_record,
}


def map_record(dataset: str, raw: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return MAPPERS[dataset](raw, metadata)
