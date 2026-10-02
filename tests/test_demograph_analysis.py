import unittest
from datetime import datetime

from src.modules.demograph.domain.analysis.party_similarity import (
    calculate,
    compare_parties,
    history_periods,
    party_at,
)

API = "https://dadosabertos.camara.leg.br/api/v2/"


def fixture():
    votings = [
        {
            "id": f"100-{index}",
            "data": "2023-02-03",
            "siglaOrgao": "PLEN",
            "descricao": "Votação nominal",
        }
        for index in range(1, 4)
    ]
    histories = [
        {
            "person_id": person,
            "dataHora": "2023-02-01T00:00:00",
            "idLegislatura": 57,
            "uriPartido": f"{API}partidos/{1 if person <= 45 else 2 if person <= 90 else 3}",
            "siglaPartido": "PT" if person <= 45 else "PSB" if person <= 90 else "PL",
        }
        for person in range(1, 101)
    ]
    votes = [
        {
            "person_id": person,
            "voting_id": f"100-{index}",
            "at": "2023-02-03T12:00:00",
            "choice": "Não"
            if (index == 1 and person > 90) or (index == 2 and 45 < person <= 90)
            else "Sim",
            "deputado_idLegislatura": "57",
            "deputado_uriPartido": f"{API}partidos/1",
        }
        for index in range(1, 4)
        for person in range(1, 101)
    ]
    return votings, votes, histories


class PartyAnalysisTest(unittest.TestCase):
    def test_majority_and_disputed_subset_match_poc(self):
        votings, votes, histories = fixture()
        result = calculate(votings, votes, histories, "2023-02-01", "2026-09-30")
        pair = next(p for p in result["pairs"] if (p["party_a_id"], p["party_b_id"]) == (1, 2))
        self.assertEqual(pair["common"], 3)
        self.assertAlmostEqual(pair["agreement"], 2 / 3)
        self.assertEqual(pair["disputed_common"], 2)
        self.assertEqual(pair["disputed_agreement"], 0.5)
        self.assertEqual(
            result["report"]["analysis_key"], "majority_sim_nao_v1:2023-02-01:2026-09-30:1:30"
        )
        self.assertEqual(result["report"]["historical_party_corrections"], 165)
        self.assertEqual(result["report"]["sufficient_pairs"], 0)

    def test_conservative_filters_duplicates_and_missing_history(self):
        votings, votes, histories = fixture()
        votings[1]["descricao"] = "Votação simbólica"
        votings[2]["siglaOrgao"] = "CCJC"
        votes.append(dict(votes[0]))
        histories = histories[:-1]
        result = calculate(votings, votes, histories, "2023-02-01", "2023-02-28", min_common=1)
        excluded = result["report"]["excluded"]
        self.assertEqual(excluded["without_roll_call_evidence"], 1)
        self.assertEqual(excluded["duplicate_vote"], 1)
        self.assertEqual(excluded["unresolved_historical_party"], 1)
        self.assertEqual(result["report"]["included_votes"], 99)
        votes[0]["choice"] = "Obstrução"
        result = calculate(votings, votes[:-1], histories, "2023-02-01", "2023-02-28")
        self.assertEqual(result["report"]["included_votings"], 0)
        self.assertEqual(result["report"]["excluded"]["non_binary_vote"], 1)
        self.assertEqual(result["report"]["excluded"]["fewer_than_100_binary_votes"], 1)

    def test_ties_absence_and_minimum_participation(self):
        def vote(voting, party, choice):
            return {
                "voting_id": voting,
                "party_id": party,
                "party_acronym": str(party),
                "choice": choice,
            }

        votes = [
            vote("v1", 1, "sim"),
            vote("v1", 2, "nao"),
            vote("v2", 1, "sim"),
            vote("v3", 1, "sim"),
            vote("v3", 1, "nao"),
            vote("v3", 2, "sim"),
        ]
        pairs, positions = compare_parties(votes)
        self.assertEqual(pairs[0]["common"], 1)
        self.assertEqual(pairs[0]["agreement"], 0)
        self.assertEqual(
            next(p for p in positions if p["voting_id"] == "v3" and p["party_id"] == 1)["majority"],
            "tie",
        )
        self.assertFalse(compare_parties(votes, 2)[0])

    def test_historical_party_boundary_conflict_and_no_current_fallback(self):
        rows = [
            {"dataHora": "2023-02-01T00:00", "siglaPartido": "A", "uriPartido": f"{API}partidos/1"},
            {"dataHora": "2024-06-01T12:00", "siglaPartido": "B", "uriPartido": f"{API}partidos/2"},
        ]
        periods = history_periods(rows)
        self.assertEqual(party_at(periods, datetime(2024, 6, 1, 11, 59)).party_id, 1)
        self.assertEqual(party_at(periods, datetime(2024, 6, 1, 12)).party_id, 2)
        self.assertIsNone(party_at(periods, datetime(2022, 1, 1)))
        with self.assertRaises(ValueError):
            history_periods([rows[0], {**rows[1], "dataHora": rows[0]["dataHora"]}])

    def test_conflicting_vote_fails_instead_of_choosing_a_side(self):
        votings, votes, histories = fixture()
        votes.append({**votes[0], "choice": "Não"})
        with self.assertRaises(ValueError):
            calculate(votings, votes, histories, "2023-02-01", "2023-02-28")

    def test_profile_and_cancellation(self):
        votings, votes, histories = fixture()

        def stop():
            raise RuntimeError("cancelled")

        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            calculate(votings, votes, histories, "2023-02-01", "2023-02-28", checkpoint=stop)
        rows = [
            {"voting_id": "v1", "party_id": p, "party_acronym": str(p), "choice": c}
            for p, c in [(1, "sim")] * 3 + [(1, "nao")] + [(2, "sim")] * 4
        ]
        self.assertEqual(compare_parties(rows)[0][0]["profile_similarity"], 0.75)
