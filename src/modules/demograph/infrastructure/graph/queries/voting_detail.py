QUERY = """
MERGE (v:Voting {camara_id: row.id}) SET v.demograph = true, v.source = $source
WITH v, row WHERE v.details_observed_at IS NULL OR v.details_observed_at <= $observed
SET v += row.properties, v.details_observed_at = $observed
WITH v, row
OPTIONAL MATCH (v)-[old:POSSIBLE_OBJECT|AFFECTS_PROPOSITION {source: $source}]->()
DELETE old
WITH DISTINCT v, row
FOREACH (prop IN row.possible |
    MERGE (p:Proposition {camara_id: prop.id})
    SET p.demograph = true, p.source = $source
    FOREACH (_ IN CASE WHEN p.observed_at IS NULL OR p.observed_at <= $observed
        THEN [1] ELSE [] END |
        SET p += prop.properties, p.observed_at = $observed
    )
    MERGE (v)-[r:POSSIBLE_OBJECT {source: $source}]->(p) SET r.demograph = true
)
FOREACH (prop IN row.affected |
    MERGE (p:Proposition {camara_id: prop.id})
    SET p.demograph = true, p.source = $source
    FOREACH (_ IN CASE WHEN p.observed_at IS NULL OR p.observed_at <= $observed
        THEN [1] ELSE [] END |
        SET p += prop.properties, p.observed_at = $observed
    )
    MERGE (v)-[r:AFFECTS_PROPOSITION {source: $source}]->(p) SET r.demograph = true
)
"""
