QUERY = """
MERGE (p:Person {camara_id: row.person_id}) SET p.demograph = true, p.source = $source
MERGE (h:DeputyHistory {key: row.key})
SET h += row.properties, h.demograph = true, h.source = $source
MERGE (p)-[r:HAS_HISTORY {source: $source}]->(h) SET r.demograph = true
"""
