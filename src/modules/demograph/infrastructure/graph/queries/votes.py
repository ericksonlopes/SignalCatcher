QUERY = """
MERGE (p:Person {camara_id: row.id})
ON CREATE SET p.name = row.name
SET p.demograph = true, p.source = $source
MERGE (v:Voting {camara_id: row.voting_id}) SET v.demograph = true, v.source = $source
MERGE (p)-[r:VOTED_IN {source: $source}]->(v)
WITH p, v, r, row WHERE r.observed_at IS NULL OR r.observed_at <= $observed
SET r += row.properties, r.choice = row.choice, r.at = row.at, r.demograph = true,
    r.observed_at = $observed, r.extraction_id = $extraction
"""
