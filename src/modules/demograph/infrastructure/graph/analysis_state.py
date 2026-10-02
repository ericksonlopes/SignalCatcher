from neo4j import ManagedTransaction

SOURCE = "CAMARA_DOS_DEPUTADOS"


def invalidate(tx: ManagedTransaction) -> None:
    """Advance the source revision in the same transaction as a graph mutation."""
    tx.run(
        "MERGE (s:DemoGraphState {key: $source}) SET s.revision = coalesce(s.revision, 0) + 1",
        source=SOURCE,
    ).consume()
    tx.run(
        "MATCH ()-[r:VOTING_POSITION|VOTING_SIMILARITY]->() "
        "WHERE r.demograph = true AND r.source = $source DELETE r",
        source=SOURCE,
    ).consume()
    tx.run(
        "MATCH (a:SimilarityAnalysis) WHERE a.demograph = true AND a.source = $source "
        "SET a.status = 'stale'",
        source=SOURCE,
    ).consume()
