import json
import logging
from pathlib import Path
from threading import Event
from typing import Any

from neo4j import Driver, GraphDatabase, ManagedTransaction

from src.modules.demograph.domain.contracts import Run
from src.modules.demograph.domain.mapping import map_record
from src.modules.demograph.infrastructure.catalog import SqlCatalog
from src.modules.demograph.infrastructure.extraction import ChamberExtractor
from src.modules.demograph.infrastructure.extraction.selection import (
    voting_ids as select_voting_ids,
)
from src.modules.demograph.infrastructure.graph.analysis_state import invalidate
from src.modules.demograph.infrastructure.graph.queries import QUERIES
from src.modules.demograph.infrastructure.storage.files import (
    checksum,
    rows,
    safe_path,
)
from src.modules.demograph.infrastructure.storage.schema import SchemaObserver

logger = logging.getLogger(__name__)

SOURCE = "CAMARA_DOS_DEPUTADOS"
# Identity constraints are compatible with the concepts used by the PoC.
KEYS = {
    "Person": "camara_id",
    "Party": "camara_id",
    "Voting": "camara_id",
    "Legislature": "camara_id",
    "State": "key",
    "PublicOffice": "key",
    "Proposition": "camara_id",
    "Topic": "key",
    "DeputyHistory": "key",
    "DemoGraphBatch": "key",
    "DemoGraphState": "key",
    "SimilarityAnalysis": "key",
}


class GraphLoader:
    def __init__(
        self,
        catalog: SqlCatalog,
        root: Path,
        uri: str | None,
        user: str,
        password: str | None,
        database: str,
        stopped: Event | None = None,
    ) -> None:
        self.catalog = catalog
        self.root = root
        self.uri, self.user, self.password, self.database = uri, user, password, database
        self.guard_adapter = ChamberExtractor(catalog, root, stopped)

    def driver(self) -> Driver:
        if not self.uri or not self.password:
            raise ValueError("Configure DEMOGRAPH_NEO4J_URI and DEMOGRAPH_NEO4J_PASSWORD.")
        return GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
            connection_timeout=10,
            max_transaction_retry_time=15,
        )

    def load(self, run: Run) -> None:
        logger.info(f"Starting load for run {run.id}")
        self.catalog.update(run.id, stage="load", schema_stale=True)
        voting_ids = select_voting_ids(self.guard_adapter, run)
        totals = {"read": 0, "outside_period": 0, "rejected": 0, "processed": 0, "duplicates": 0}
        by_dataset: dict[str, dict[str, int]] = {}
        seen_votes: dict[tuple[str, int], str] = {}
        try:
            with self.driver() as driver:
                logger.info(f"Connecting to Neo4j at {self.uri}")
                driver.verify_connectivity()
                with driver.session(database=self.database) as session:
                    logger.info("Setting up Neo4j constraints")
                    for label, prop in KEYS.items():
                        session.run(
                            f"CREATE CONSTRAINT demograph_{label.lower()} IF NOT EXISTS "
                            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                        ).consume()
                    logger.info(f"Processing artifacts for extraction {run.extraction_id}")
                    for artifact in self.catalog.artifacts(run.extraction_id):
                        self.guard_adapter.guard(run.id)
                        path = safe_path(self.root, artifact["path"])
                        if not path.is_file() or checksum(path) != artifact["checksum"]:
                            raise ValueError(f"Artifact checksum mismatch for {path}.")
                        dataset = artifact["dataset_id"]
                        counters = by_dataset.setdefault(dataset, {key: 0 for key in totals})
                        self.catalog.update(run.id, stage=f"load:{dataset}")
                        batch: list[dict[str, Any]] = []
                        batch_number = 0
                        for index, raw in enumerate(rows(path, artifact["metadata_json"])):
                            totals["read"] += 1
                            counters["read"] += 1
                            if index % 1000 == 0:
                                self.guard_adapter.guard(run.id)
                            if (dataset == "votings" and str(raw.get("id")) not in voting_ids) or (
                                dataset == "votes" and str(raw.get("idVotacao")) not in voting_ids
                            ):
                                totals["outside_period"] += 1
                                counters["outside_period"] += 1
                                continue
                            try:
                                mapped = map_record(dataset, raw, artifact["metadata_json"])
                                if dataset == "votes":
                                    key = (mapped["voting_id"], mapped["id"])
                                    if key in seen_votes:
                                        if seen_votes[key] != mapped["choice"]:
                                            raise ValueError(
                                                "Conflicting votes in this extraction."
                                            )
                                        totals["duplicates"] += 1
                                        counters["duplicates"] += 1
                                        continue
                                    seen_votes[key] = mapped["choice"]
                            except (ValueError, KeyError, TypeError) as exc:
                                totals["rejected"] += 1
                                counters["rejected"] += 1
                                self.catalog.issue(
                                    run.id,
                                    "Invalid record.",
                                    {
                                        "artifact_id": artifact["id"],
                                        "row": index + 1,
                                        "type": type(exc).__name__,
                                    },
                                )
                                continue
                            batch.append(mapped)
                            if len(batch) == 500:
                                session.execute_write(
                                    self.write_batch, run, artifact, batch_number, batch
                                )
                                totals["processed"] += len(batch)
                                counters["processed"] += len(batch)
                                self.catalog.progress(
                                    run.id, load=totals, load_by_dataset=by_dataset
                                )
                                batch, batch_number = [], batch_number + 1
                                self.guard_adapter.guard(run.id)
                        if batch:
                            session.execute_write(
                                self.write_batch, run, artifact, batch_number, batch
                            )
                            totals["processed"] += len(batch)
                            counters["processed"] += len(batch)
                        elif artifact["records"] == 0:
                            session.execute_write(self.write_batch, run, artifact, batch_number, [])
                        self.catalog.progress(run.id, load=totals, load_by_dataset=by_dataset)
            self.catalog.progress(run.id, load_complete=True)
            logger.info(f"Load complete for run {run.id}")
        except Exception as exc:
            logger.error(f"Error during load phase for run {run.id}: {exc}", exc_info=True)
            raise

    @staticmethod
    def write_batch(
        tx: ManagedTransaction,
        run: Run,
        artifact: dict[str, Any],
        number: int,
        batch: list[dict[str, Any]],
    ) -> None:
        token = f"{run.id}:{artifact['id']}:{number}"
        record = tx.run(
            "MATCH (b:DemoGraphBatch {key: $key}) RETURN b.key AS key", key=token
        ).single()
        if record:
            return
        invalidate(tx)
        kind = artifact["metadata_json"].get("kind", artifact["dataset_id"])
        observed = run.parameters.get("snapshot_at", artifact["collected_at"].isoformat())
        if (
            kind == "proposition_topics"
            and number == 0
            and artifact["metadata_json"].get("page", 1) == 1
            and not artifact["metadata_json"].get("unavailable")
        ):
            tx.run(
                "MERGE (p:Proposition {camara_id: $id}) SET p.demograph = true, p.source = $source "
                "WITH p WHERE p.topics_observed_at IS NULL OR p.topics_observed_at <= $observed "
                "OPTIONAL MATCH (p)-[r:HAS_TOPIC {source: $source}]->() DELETE r "
                "WITH DISTINCT p SET p.topics_observed_at = $observed",
                id=artifact["metadata_json"]["proposition_id"],
                source=SOURCE,
                observed=observed,
            ).consume()
        tx.run(
            "UNWIND $rows AS row\n" + QUERIES[kind],
            rows=batch,
            observed=observed,
            source=SOURCE,
            extraction=run.extraction_id,
        ).consume()
        tx.run(
            "CREATE (b:DemoGraphBatch {key: $key, run_id: $run, artifact_id: $artifact, "
            "records: $records, observed_at: $observed, extraction_id: $extraction, "
            "payload_json: $payload})",
            key=token,
            run=run.id,
            artifact=artifact["id"],
            records=len(batch),
            observed=observed,
            extraction=run.extraction_id,
            payload=json.dumps(
                {
                    "kind": kind,
                    "number": number,
                    "metadata": artifact["metadata_json"],
                    "path": artifact["path"],
                    "rows": batch,
                }
            ),
        ).consume()

    def delete_extraction(self, extraction_id: str, run_ids: list[str]) -> dict[str, int]:
        from src.modules.demograph.infrastructure.graph.deletion import delete_extraction

        return delete_extraction(self, extraction_id, run_ids)

    def schema(self, run_id: str | None = None) -> dict[str, Any]:
        nodes: dict[str, SchemaObserver] = {}
        relationships: dict[tuple[str, str, str], SchemaObserver] = {}
        with self.driver() as driver, driver.session(database=self.database) as session:
            for index, record in enumerate(
                session.run(
                    "MATCH (n) WHERE n.demograph = true "
                    "RETURN labels(n) AS labels, properties(n) AS props"
                )
            ):
                if run_id and index % 1000 == 0:
                    self.guard_adapter.guard(run_id)
                if self.guard_adapter.stopped.is_set():
                    raise RuntimeError("Worker stopped while observing schema.")
                for label in record["labels"]:
                    nodes.setdefault(label, SchemaObserver()).observe(dict(record["props"]))
            for index, record in enumerate(
                session.run(
                    "MATCH (a)-[r]->(b) WHERE r.demograph = true "
                    "RETURN labels(a) AS starts, type(r) AS type, "
                    "labels(b) AS ends, properties(r) AS props"
                )
            ):
                if run_id and index % 1000 == 0:
                    self.guard_adapter.guard(run_id)
                if self.guard_adapter.stopped.is_set():
                    raise RuntimeError("Worker stopped while observing schema.")
                for start in record["starts"]:
                    for end in record["ends"]:
                        key = (start, record["type"], end)
                        relationships.setdefault(key, SchemaObserver()).observe(
                            dict(record["props"])
                        )
            constraints = [
                dict(record)
                for record in session.run(
                    "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties "
                    "WHERE name STARTS WITH 'demograph_' "
                    "RETURN name, type, labelsOrTypes, properties"
                )
            ]
        return {
            "nodes": [
                {"label": label, "count": observer.count, "properties": observer.result()["fields"]}
                for label, observer in sorted(nodes.items())
            ],
            "relationships": [
                {
                    "source": start,
                    "type": kind,
                    "target": end,
                    "count": observer.count,
                    "properties": observer.result()["fields"],
                }
                for (start, kind, end), observer in sorted(relationships.items())
            ],
            "constraints": constraints,
        }
