"""Reconstruct the managed graph from confirmed receipts in one transaction."""

import json
from typing import TYPE_CHECKING, Any

from neo4j import ManagedTransaction

from src.modules.demograph.domain.mapping import map_record
from src.modules.demograph.infrastructure.graph.queries import QUERIES
from src.modules.demograph.infrastructure.storage.files import checksum, rows, safe_path

if TYPE_CHECKING:
    from src.modules.demograph.infrastructure.graph.loader import GraphLoader


def legacy_payloads(loader: "GraphLoader", run_id: str) -> dict[str, str]:
    """Recover the exact 500-row batches used before receipts contained payloads."""
    run = loader.catalog.run(run_id)
    artifacts = loader.catalog.artifacts(run.extraction_id)
    for artifact in artifacts:
        path = safe_path(loader.root, artifact["path"])
        if not path.is_file() or checksum(path) != artifact["checksum"]:
            raise ValueError("Cannot recover a legacy load: an artifact is missing or changed.")
    selected = {
        str(row["id"])
        for artifact in artifacts
        if artifact["dataset_id"] == "votings"
        for row in rows(safe_path(loader.root, artifact["path"]), artifact["metadata_json"])
        if run.parameters["start"] <= row["data"] <= run.parameters["end"]
    }
    result: dict[str, str] = {}
    seen: dict[tuple[str, int], str] = {}
    for artifact in artifacts:
        dataset = artifact["dataset_id"]
        batch: list[dict[str, Any]] = []
        number = 0

        def publish() -> None:
            result[f"{run.id}:{artifact['id']}:{number}"] = json.dumps(
                {
                    "kind": artifact["metadata_json"].get("kind", dataset),
                    "number": number,
                    "metadata": artifact["metadata_json"],
                    "path": artifact["path"],
                    "extraction_id": run.extraction_id,
                    "rows": batch,
                }
            )

        for raw in rows(safe_path(loader.root, artifact["path"]), artifact["metadata_json"]):
            if (dataset == "votings" and str(raw.get("id")) not in selected) or (
                dataset == "votes" and str(raw.get("idVotacao")) not in selected
            ):
                continue
            try:
                mapped = map_record(dataset, raw, artifact["metadata_json"])
                if dataset == "votes":
                    key = (mapped["voting_id"], mapped["id"])
                    if key in seen:
                        continue
                    seen[key] = mapped["choice"]
            except (ValueError, KeyError, TypeError):
                continue
            batch.append(mapped)
            if len(batch) == 500:
                publish()
                batch, number = [], number + 1
        if batch or artifact["records"] == 0:
            publish()
    return result


def delete_extraction(
    loader: "GraphLoader", extraction_id: str, run_ids: list[str]
) -> dict[str, int]:
    from src.modules.demograph.infrastructure.graph.loader import KEYS, SOURCE

    with loader.driver() as driver, driver.session(database=loader.database) as session:
        # Preflight legacy recovery before changing anything in Neo4j or storage.
        legacy: dict[str, str] = {}
        for record in session.run(
            "MATCH (b:DemoGraphBatch) WHERE b.payload_json IS NULL "
            "AND NOT b.run_id IN $runs RETURN DISTINCT b.run_id AS run",
            runs=run_ids,
        ):
            legacy.update(legacy_payloads(loader, record["run"]))

        def remove(tx: ManagedTransaction) -> dict[str, int]:
            retained = []
            deleted_batches = 0
            for record in tx.run("MATCH (b:DemoGraphBatch) RETURN properties(b) AS receipt"):
                receipt = dict(record["receipt"])
                if receipt["run_id"] in run_ids or receipt.get("extraction_id") == extraction_id:
                    deleted_batches += 1
                    continue
                payload = receipt.get("payload_json") or legacy.get(receipt["key"])
                if not payload:
                    raise ValueError("A confirmed load cannot be recovered safely.")
                receipt["payload_json"] = payload
                receipt["payload"] = json.loads(payload)
                # Validate before the first mutation; unknown receipt versions abort.
                if receipt["payload"]["kind"] not in QUERIES:
                    raise ValueError("Unknown confirmed load format.")
                retained.append(receipt)
            if not deleted_batches:
                return {"batches": 0}
            # Remove only managed edges. Foreign relationships protect their nodes.
            tx.run(
                "MATCH ()-[r]->() WHERE r.demograph = true AND r.source = $source DELETE r",
                source=SOURCE,
            ).consume()
            tx.run(
                "MATCH (n) WHERE n.demograph = true "
                "AND any(label IN labels(n) WHERE label IN $labels) "
                "AND NOT (n)--() DELETE n",
                labels=[label for label in KEYS if label != "DemoGraphBatch"],
            ).consume()
            tx.run(
                "MATCH (n) WHERE n.demograph = true "
                "REMOVE n.demograph, n.source, n.observed_at, "
                "n.details_observed_at, n.topics_observed_at"
            ).consume()
            tx.run(
                "MATCH (b:DemoGraphBatch) WHERE b.run_id IN $runs "
                "OR b.extraction_id = $extraction DELETE b",
                runs=run_ids,
                extraction=extraction_id,
            ).consume()
            for receipt in sorted(
                retained,
                key=lambda item: (
                    item["observed_at"],
                    item["run_id"],
                    item["payload"].get("path", ""),
                    item["payload"]["number"],
                ),
            ):
                payload = receipt["payload"]
                metadata = payload["metadata"]
                if (
                    payload["kind"] == "proposition_topics"
                    and payload["number"] == 0
                    and metadata.get("page", 1) == 1
                    and not metadata.get("unavailable")
                ):
                    tx.run(
                        "MERGE (p:Proposition {camara_id: $id}) "
                        "SET p.demograph = true, p.source = $source "
                        "WITH p OPTIONAL MATCH (p)-[r:HAS_TOPIC {source: $source}]->() DELETE r "
                        "WITH DISTINCT p SET p.topics_observed_at = $observed",
                        id=metadata["proposition_id"],
                        source=SOURCE,
                        observed=receipt["observed_at"],
                    ).consume()
                tx.run(
                    "UNWIND $rows AS row\n" + QUERIES[payload["kind"]],
                    rows=payload["rows"],
                    observed=receipt["observed_at"],
                    source=SOURCE,
                    extraction=receipt.get("extraction_id") or payload["extraction_id"],
                ).consume()
                tx.run(
                    "MATCH (b:DemoGraphBatch {key: $key}) "
                    "SET b.payload_json = $payload, b.extraction_id = $extraction",
                    key=receipt["key"],
                    payload=receipt["payload_json"],
                    extraction=receipt.get("extraction_id") or payload["extraction_id"],
                ).consume()
            return {"batches": deleted_batches}

        return session.execute_write(remove)
