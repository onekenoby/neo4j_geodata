# neo4j_utils.py
from neo4j import GraphDatabase
from config import NEO4J_URI, USERNAME, PASSWORD, GDS_GRAPH_NAME

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(USERNAME, PASSWORD),
    max_connection_pool_size=50,
    connection_timeout=30
)

def ensure_gds_graph():
    """
    Project the OperationPoint–SECTION graph into memory for GDS if not already.
    """
    with driver.session() as ses:
        exists = ses.run(
            "CALL gds.graph.exists($name) YIELD exists RETURN exists",
            name=GDS_GRAPH_NAME
        ).single()["exists"]
        if not exists:
            ses.run(f"""
                CALL gds.graph.project(
                  '{GDS_GRAPH_NAME}',
                  'OperationPoint',
                  {{
                    SECTION: {{
                      type: 'SECTION',
                      properties: 'sectionlength',
                      orientation: 'UNDIRECTED'
                    }}
                  }}
                )
            """)

def get_all_point_coords():
    """
    Return list of dicts {id,label,country,lat,lon} for every OperationPoint.
    """
    with driver.session() as ses:
        q = """
        MATCH (op:OperationPoint)
        OPTIONAL MATCH (op)-[:NAMED]->(pn:OperationPointName)
        OPTIONAL MATCH (op)-[r:NAMED]->()
        RETURN op.id AS id,
               coalesce(pn.name, op.id) AS label,
               r.country      AS country,
               op.geolocation.latitude  AS lat,
               op.geolocation.longitude AS lon
        ORDER BY label
        """
        result = ses.run(q)
        return [
            {
                "id": rec["id"],
                "label": rec["label"],
                "country": rec["country"] or "Unknown",
                "lat": rec["lat"],
                "lon": rec["lon"]
            }
            for rec in result
        ]

def get_minimal_path_dijkstra(src_prop_id: str, dst_prop_id: str):
    """
    Compute the true minimal path between two OperationPoint IDs using GDS Dijkstra.
    Returns a list with one dict: {cities, edges, total_distance}.
    """
    with driver.session() as ses:
        # lookup internal node IDs
        endpoints = ses.run(
            "MATCH (s:OperationPoint {id:$src}), (t:OperationPoint {id:$dst})"
            " RETURN id(s) AS sId, id(t) AS tId",
            src=src_prop_id, dst=dst_prop_id
        ).single()
        if not endpoints:
            return []
        sId, tId = endpoints["sId"], endpoints["tId"]

        # run Dijkstra
        path_rec = ses.run(f"""
            CALL gds.shortestPath.dijkstra.stream(
              '{GDS_GRAPH_NAME}',
              {{ sourceNode: $sId, targetNode: $tId, relationshipWeightProperty: 'sectionlength' }}
            )
            YIELD nodeIds, costs
            RETURN nodeIds, costs AS totalDistance
        """, sId=sId, tId=tId).single()
        if not path_rec:
            return []

        node_ids = path_rec["nodeIds"]
        total    = path_rec["totalDistance"]

        # fetch node properties
        cities = []
        for nid in node_ids:
            r = ses.run(
                "MATCH (op:OperationPoint) WHERE id(op) = $nid"
                " RETURN op.id AS id, op.id AS label, op.geolocation.latitude AS lat, op.geolocation.longitude AS lon",
                nid=nid
            ).single()
            cities.append({
                "id":    r["id"],
                "label": r["label"],
                "lat":   r["lat"],
                "lon":   r["lon"]
            })

        # build edges with distances
        edges = []
        for a, b in zip(cities, cities[1:]):
            rel = ses.run(
                "MATCH (a:OperationPoint {id:$id1})-[r:SECTION]-(b:OperationPoint {id:$id2})"
                " RETURN r.sectionlength AS dist",
                id1=a["id"], id2=b["id"]
            ).single()
            edges.append({
                "source":   a["id"],
                "target":   b["id"],
                "distance": rel["dist"] if rel else None
            })

        return [{"cities": cities, "edges": edges, "total_distance": total}]