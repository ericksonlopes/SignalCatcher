QUERY = """
MERGE (p:Proposition {camara_id: row.proposition_id}) SET p.demograph = true, p.source = $source
WITH p, row WHERE p.topics_observed_at IS NULL OR p.topics_observed_at <= $observed
MERGE (t:Topic {key: $source + ':' + toString(row.code)})
SET t.code = row.code, t.demograph = true
FOREACH (_ IN CASE WHEN t.observed_at IS NULL OR t.observed_at <= $observed THEN [1] ELSE [] END |
    SET t.name = row.name, t.observed_at = $observed
)
MERGE (p)-[r:HAS_TOPIC {source: $source}]->(t) SET r.demograph = true, r.observed_at = $observed
"""
