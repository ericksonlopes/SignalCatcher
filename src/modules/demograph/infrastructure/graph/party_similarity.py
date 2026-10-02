import json
from collections.abc import Iterator
from typing import Any

from neo4j import ManagedTransaction

from src.modules.demograph.domain.analysis.party_similarity import calculate
from src.modules.demograph.domain.contracts import Run
from src.modules.demograph.infrastructure.graph.loader import SOURCE, GraphLoader


class PartySimilarity:
    def __init__(self, graph: GraphLoader) -> None:
        self.graph = graph

    def analyze(self, run: Run) -> None:
        catalog = self.graph.catalog
        catalog.update(run.id, stage="analysis", schema_stale=True)
        self.graph.guard_adapter.guard(run.id)
        with self.graph.driver() as driver, driver.session(database=self.graph.database) as session:
            for label, prop in (("SimilarityAnalysis", "key"), ("DemoGraphState", "key")):
                session.run(
                    f"CREATE CONSTRAINT demograph_{label.lower()} IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                ).consume()
            result, revision = session.execute_read(self.read, run)
            self.graph.guard_adapter.guard(run.id)
            session.execute_write(self.publish, run, result, revision)
        catalog.progress(run.id, analysis=result["report"], analysis_complete=True)

    def read(self, tx: ManagedTransaction, run: Run) -> tuple[dict[str, Any], int]:
        def revision() -> int:
            row = tx.run(
                "OPTIONAL MATCH (s:DemoGraphState {key: $source}) RETURN coalesce(s.revision, "
                "0) AS revision",
                source=SOURCE,
            ).single()
            assert row is not None
            return int(row["revision"])

        initial = revision()

        def records(query: str) -> Iterator[dict[str, Any]]:
            for record in tx.run(
                query, source=SOURCE, start=run.parameters["start"], end=run.parameters["end"]
            ):
                yield dict(record["row"])

        result = calculate(
            records(
                "MATCH (v:Voting) WHERE v.demograph = true AND v.source = $source "
                "AND v.date >= $start AND v.date <= $end "
                "RETURN {id: v.camara_id, data: v.date, siglaOrgao: v.siglaOrgao, descricao: "
                "v.description} AS row"
            ),
            records(
                "MATCH (p:Person)-[r:VOTED_IN]->(v:Voting) "
                "WHERE r.demograph = true AND r.source = $source AND v.date >= $start AND "
                "v.date <= $end "
                "RETURN {voting_id: v.camara_id, person_id: p.camara_id, choice: r.choice, at: "
                "r.at, "
                "deputado_idLegislatura: r.deputado_idLegislatura, deputado_uriPartido: "
                "r.deputado_uriPartido} AS row"
            ),
            records(
                "MATCH (p:Person)-[r:HAS_HISTORY]->(h:DeputyHistory) "
                "WHERE r.demograph = true AND r.source = $source "
                "RETURN {person_id: p.camara_id, dataHora: h.dataHora, idLegislatura: "
                "h.idLegislatura, "
                "uriPartido: h.uriPartido, siglaPartido: h.siglaPartido} AS row"
            ),
            run.parameters["start"],
            run.parameters["end"],
            run.parameters["min_party_votes"],
            run.parameters["min_common"],
            lambda: self.graph.guard_adapter.guard(run.id),
        )
        if revision() != initial:
            raise ValueError("Graph changed during analysis. Retry after loading finishes.")
        result["report"]["source_revision"] = initial
        return result, initial

    def publish(
        self, tx: ManagedTransaction, run: Run, result: dict[str, Any], revision: int
    ) -> None:
        self.graph.guard_adapter.guard(run.id)
        # A zero increment checks the current revision atomically with publication.
        record = tx.run(
            "MERGE (s:DemoGraphState {key: $source}) "
            "SET s.revision = coalesce(s.revision, 0) + 0 RETURN s.revision AS revision",
            source=SOURCE,
        ).single()
        if record is None or record["revision"] != revision:
            raise ValueError("Graph changed during analysis. Retry after loading finishes.")
        report = result["report"]
        key = report["analysis_key"]
        tx.run(
            "MATCH ()-[r:VOTING_POSITION|VOTING_SIMILARITY]->() "
            "WHERE r.analysis_key = $key AND r.demograph = true AND r.source = $source DELETE r",
            key=key,
            source=SOURCE,
        ).consume()
        metadata = {name: value for name, value in report.items() if name != "excluded"}
        metadata["excluded_json"] = json.dumps(report["excluded"])
        tx.run(
            "MERGE (a:SimilarityAnalysis {key: $key}) SET a += $metadata, "
            "a.demograph = true, a.source = $source, a.status = 'completed', "
            "a.run_id = $run, a.source_revision = $revision, a.updated_at = datetime()",
            key=key,
            metadata=metadata,
            source=SOURCE,
            run=run.id,
            revision=revision,
        ).consume()
        for offset in range(0, len(result["positions"]), 500):
            self.graph.guard_adapter.guard(run.id)
            tx.run(
                "UNWIND $rows AS row MERGE (p:Party {camara_id: row.party_id}) "
                "ON CREATE SET p.acronym = row.party_acronym, p.demograph = true, p.source = "
                "$source "
                "WITH p, row MATCH (v:Voting {camara_id: row.voting_id}) "
                "MERGE (p)-[r:VOTING_POSITION {analysis_key: $key}]->(v) "
                "SET r += row, r.demograph = true, r.source = $source",
                rows=result["positions"][offset : offset + 500],
                key=key,
                source=SOURCE,
            ).consume()
        for offset in range(0, len(result["pairs"]), 500):
            self.graph.guard_adapter.guard(run.id)
            tx.run(
                "UNWIND $rows AS row MATCH (a:Party {camara_id: row.party_a_id}), (b:Party "
                "{camara_id: row.party_b_id}) "
                "MERGE (a)-[r:VOTING_SIMILARITY {analysis_key: $key}]->(b) "
                "SET r.agreement = row.agreement, r.common_votes = row.common, "
                "r.disputed_agreement = row.disputed_agreement, r.disputed_common_votes = "
                "row.disputed_common, "
                "r.profile_similarity = row.profile_similarity, r.demograph = true, r.source = "
                "$source, "
                "r.sample_status = CASE WHEN row.disputed_common >= $minimum THEN 'sufficient' "
                "ELSE 'insufficient' END",
                rows=result["pairs"][offset : offset + 500],
                key=key,
                source=SOURCE,
                minimum=report["min_common"],
            ).consume()
        self.graph.guard_adapter.guard(run.id)
