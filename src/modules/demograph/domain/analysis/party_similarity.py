"""Party majority comparison ported from the DemoGraph PoC, method v1."""

import re
import unicodedata
from bisect import bisect_right
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import date, datetime
from itertools import combinations
from typing import Any

from src.modules.demograph.domain.mapping.common import identity

METHOD = "majority_sim_nao_v1"


def calculate(
    votings: Iterable[dict[str, Any]],
    votes: Iterable[dict[str, Any]],
    histories: Iterable[dict[str, Any]],
    start: str,
    end: str,
    min_party_votes: int = 1,
    min_common: int = 30,
    checkpoint: Callable[[], None] = lambda: None,
) -> dict[str, Any]:
    if date.fromisoformat(start) > date.fromisoformat(end) or min_party_votes < 1 or min_common < 1:
        raise ValueError("Invalid analysis parameters.")
    excluded: Counter[str] = Counter()
    history_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, history in enumerate(histories):
        if index % 1000 == 0:
            checkpoint()
        history_rows[int(history["person_id"])].append(history)
    periods = {person: history_periods(records) for person, records in history_rows.items()}
    selected: set[str] = set()
    listed = 0
    observed_dates: list[str] = []
    for index, voting in enumerate(votings):
        if index % 1000 == 0:
            checkpoint()
        if start <= str(voting.get("data", "")) <= end:
            observed_dates.append(str(voting["data"]))
        if not start <= str(voting.get("data", "")) <= end or voting.get("siglaOrgao") != "PLEN":
            continue
        listed += 1
        description = folded(str(voting.get("descricao", "")))
        evidence = "votacao nominal" in description or (
            re.search(r"\bsim\s*:\s*\d+", description)
            and re.search(r"\bnao\s*:\s*\d+", description)
        )
        if "simbolic" in description or not evidence:
            excluded["without_roll_call_evidence"] += 1
            continue
        selected.add(str(voting["id"]))
    eligible_votes: list[dict[str, Any]] = []
    seen: dict[tuple[str, int], str] = {}
    for index, raw in enumerate(votes):
        if index % 1000 == 0:
            checkpoint()
        voting_id = str(raw["voting_id"])
        if voting_id not in selected:
            continue
        if str(raw.get("deputado_idLegislatura")) != "57":
            excluded["outside_legislature"] += 1
            continue
        choice = folded(str(raw["choice"]).strip())
        if choice not in {"sim", "nao"}:
            excluded["non_binary_vote"] += 1
            continue
        try:
            person = int(raw["person_id"])
            datetime.fromisoformat(raw["at"])
            if person <= 0:
                raise ValueError("Invalid person identity.")
        except (ValueError, TypeError, KeyError):
            excluded["invalid_vote"] += 1
            continue
        key = (voting_id, person)
        if key in seen:
            if seen[key] != choice:
                raise ValueError("Conflicting votes for the same person and voting.")
            excluded["duplicate_vote"] += 1
            continue
        seen[key] = choice
        eligible_votes.append({**raw, "choice": choice, "person_id": person})
    counts = Counter(vote["voting_id"] for vote in eligible_votes)
    small = {voting for voting in selected if counts[voting] < 100}
    excluded["fewer_than_100_binary_votes"] = len(small)
    selected -= small
    resolved: list[dict[str, Any]] = []
    corrections = 0
    for index, vote in enumerate(eligible_votes):
        if index % 1000 == 0:
            checkpoint()
        if vote["voting_id"] not in selected:
            continue
        period = party_at(periods.get(vote["person_id"], []), datetime.fromisoformat(vote["at"]))
        if period is None:
            excluded["unresolved_historical_party"] += 1
            continue
        corrections += int(period.uri != vote.get("deputado_uriPartido"))
        resolved.append({**vote, "party_id": period.party_id, "party_acronym": period.acronym})
    pairs, positions = compare_parties(resolved, min_party_votes, checkpoint)
    report = {
        "analysis_key": f"{METHOD}:{start}:{end}:{min_party_votes}:{min_common}",
        "method": METHOD,
        "start_date": start,
        "end_date": end,
        "listed_plenary_votings": listed,
        "observed_start_date": min(observed_dates) if observed_dates else None,
        "observed_end_date": max(observed_dates) if observed_dates else None,
        "included_votings": len(selected),
        "included_votes": len(resolved),
        "parties": len({v["party_id"] for v in resolved}),
        "historical_party_corrections": corrections,
        "excluded": dict(excluded),
        "min_common": min_common,
        "min_party_votes": min_party_votes,
        "compared_pairs": len(pairs),
        "sufficient_pairs": sum(p["disputed_common"] >= min_common for p in pairs),
    }
    return {"report": report, "pairs": pairs, "positions": positions}


def folded(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    ).lower()


@dataclass(frozen=True)
class PartyPeriod:
    at: datetime
    party_id: int
    acronym: str
    uri: str


def history_periods(rows: list[dict[str, Any]]) -> list[PartyPeriod]:
    periods = []
    for row in rows:
        if row.get("idLegislatura", 57) != 57:
            continue
        if not row.get("uriPartido") or not row.get("siglaPartido"):
            continue
        periods.append(
            PartyPeriod(
                datetime.fromisoformat(row["dataHora"]),
                identity(row["uriPartido"], "partidos"),
                row["siglaPartido"].strip().upper(),
                row["uriPartido"],
            )
        )
    periods.sort(key=lambda period: period.at)
    for previous, current in zip(periods, periods[1:], strict=False):
        if previous.at == current.at and previous.party_id != current.party_id:
            raise ValueError("Conflicting historical parties at the same timestamp.")
    return periods


def party_at(periods: list[PartyPeriod], at: datetime) -> PartyPeriod | None:
    index = bisect_right([period.at for period in periods], at) - 1
    return periods[index] if index >= 0 else None


@dataclass
class PairScore:
    party_a_id: int
    party_b_id: int
    party_a: str
    party_b: str
    common: int = 0
    agreed: int = 0
    disputed_common: int = 0
    disputed_agreed: int = 0
    profile_sum: float = 0

    def result(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "agreement": self.agreed / self.common if self.common else None,
            "disputed_agreement": self.disputed_agreed / self.disputed_common
            if self.disputed_common
            else None,
            "profile_similarity": self.profile_sum / self.common if self.common else None,
        }


def compare_parties(
    votes: list[dict[str, Any]],
    min_party_votes: int = 1,
    checkpoint: Callable[[], None] = lambda: None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ballots: dict[str, dict[int, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    names: dict[int, str] = {}
    for vote in votes:
        ballots[vote["voting_id"]][vote["party_id"]][vote["choice"]] += 1
        names[vote["party_id"]] = vote["party_acronym"]
    pairs: dict[tuple[int, int], PairScore] = {}
    positions = []
    for index, (voting_id, parties) in enumerate(ballots.items()):
        if index % 1000 == 0:
            checkpoint()
        total_yes = sum(counts["sim"] for counts in parties.values())
        total_no = sum(counts["nao"] for counts in parties.values())
        disputed = min(total_yes, total_no) / (total_yes + total_no) >= 0.10
        eligible = {}
        for party_id, counts in parties.items():
            total = counts["sim"] + counts["nao"]
            share = counts["sim"] / total
            majority = "tie" if share == 0.5 else "sim" if share > 0.5 else "nao"
            positions.append(
                {
                    "voting_id": voting_id,
                    "party_id": party_id,
                    "party_acronym": names[party_id],
                    "yes": counts["sim"],
                    "no": counts["nao"],
                    "yes_share": share,
                    "majority": majority,
                    "cohesion": max(share, 1 - share),
                    "disputed": disputed,
                }
            )
            if total >= min_party_votes and majority != "tie":
                eligible[party_id] = (majority, share)
        for a, b in combinations(sorted(eligible), 2):
            pair = pairs.setdefault((a, b), PairScore(a, b, names[a], names[b]))
            same = eligible[a][0] == eligible[b][0]
            pair.common += 1
            pair.agreed += int(same)
            pair.profile_sum += 1 - abs(eligible[a][1] - eligible[b][1])
            if disputed:
                pair.disputed_common += 1
                pair.disputed_agreed += int(same)
    return [pair.result() for pair in pairs.values()], positions
