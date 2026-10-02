from src.modules.demograph.infrastructure.graph.queries.deputies import QUERY as DEPUTIES
from src.modules.demograph.infrastructure.graph.queries.histories import QUERY as HISTORIES
from src.modules.demograph.infrastructure.graph.queries.proposition_topics import (
    QUERY as PROPOSITION_TOPICS,
)
from src.modules.demograph.infrastructure.graph.queries.votes import QUERY as VOTES
from src.modules.demograph.infrastructure.graph.queries.voting_detail import QUERY as VOTING_DETAIL
from src.modules.demograph.infrastructure.graph.queries.votings import QUERY as VOTINGS

QUERIES = {
    "deputies": DEPUTIES,
    "votings": VOTINGS,
    "votes": VOTES,
    "histories": HISTORIES,
    "voting_detail": VOTING_DETAIL,
    "proposition_topics": PROPOSITION_TOPICS,
}
