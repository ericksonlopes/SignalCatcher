PERSON = """
MERGE (p:Person {camara_id: row.id})
SET p.demograph = true, p.source = $source
"""

QUERY = (
    PERSON
    + """
WITH p, row WHERE p.observed_at IS NULL OR p.observed_at <= $observed
SET p += row.properties, p.name = row.name, p.observed_at = $observed
MERGE (s:State {key: 'BR:' + row.state})
SET s.code = row.state, s.country = 'BR', s.demograph = true
MERGE (l:Legislature {camara_id: row.legislature}) SET l.demograph = true
MERGE (o:PublicOffice {key: 'DEPUTADO_FEDERAL'}) SET o.demograph = true, o.name = 'Deputado Federal'
WITH p, row, s, l, o
OPTIONAL MATCH (p)-[old:AFFILIATED_WITH|REPRESENTS {source: $source}]->()
DELETE old
WITH DISTINCT p, row, s, l, o
MERGE (p)-[rs:REPRESENTS {source: $source}]->(s)
SET rs.demograph = true, rs.observed_at = $observed
MERGE (p)-[rl:SERVED_IN {source: $source}]->(l) SET rl.demograph = true
MERGE (p)-[ro:HOLDS_OFFICE {source: $source}]->(o) SET ro.demograph = true
FOREACH (_ IN CASE WHEN row.party_id IS NULL THEN [] ELSE [1] END |
    MERGE (party:Party {camara_id: row.party_id})
    SET party.demograph = true
    FOREACH (_ IN CASE WHEN party.observed_at IS NULL OR party.observed_at <= $observed
        THEN [1] ELSE [] END |
        SET party.acronym = row.party_name, party.observed_at = $observed
    )
    MERGE (p)-[rp:AFFILIATED_WITH {source: $source}]->(party)
    SET rp.demograph = true, rp.observed_at = $observed
)
"""
)
