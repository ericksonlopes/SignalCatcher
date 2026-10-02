QUERY = """
MERGE (v:Voting {camara_id: row.id}) SET v.demograph = true, v.source = $source
WITH v, row WHERE v.observed_at IS NULL OR v.observed_at <= $observed
SET v += row.properties, v.date = row.date,
    v.description = row.description, v.observed_at = $observed
"""
