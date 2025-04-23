# neo4j_utils.py

from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASS, GDS_GRAPH_NAME



driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS), max_connection_pool_size=50)

def get_all_countries():
    """
    Return a sorted list of all distinct country codes from NAMED relationships.
    """
    with driver.session() as ses:
        result = ses.run("""
            MATCH ()-[r:NAMED]->()
            RETURN DISTINCT r.country AS country
            ORDER BY r.country
        """)
        return [r["country"] for r in result]

def get_all_point_coords():
    """
    Return list of dicts {id, label, country, lat, lon} for every OperationPoint.
    """
    with driver.session() as ses:
        result = ses.run("""
            MATCH (op:OperationPoint)-[r:NAMED]->(pn:OperationPointName)
            RETURN
              op.id     AS id,
              pn.name   AS label,
              r.country AS country,
              op.geolocation.latitude  AS lat,
              op.geolocation.longitude AS lon
            ORDER BY pn.name
        """)
        return [
            {
              "id": rec["id"],
              "label": rec["label"],
              "country": rec["country"],
              "lat": rec["lat"],
              "lon": rec["lon"]
            }
            for rec in result
        ]

# ... (rest of your get_top_paths, ensure_gds_graph, close_driver unchanged) ...

def get_top_paths_gds(source_id: str, target_id: str, k: int = 3):
    """
    Use GDS Yen’s algorithm to get the top-k shortest paths.
    """
    query = f"""
    CALL gds.shortestPath.yens.stream(
      '{GDS_GRAPH_NAME}',
      {{ startNode: $src, endNode: $dst, k: $k, relationshipWeightProperty: 'sectionlength' }}
    )
    YIELD path, cost
    RETURN path, cost AS total_distance
    """
    paths = []
    with driver.session() as ses:
        for rec in ses.run(query, src=source_id, dst=target_id, k=k):
            nodes = rec["path"].nodes
            rels  = rec["path"].relationships
            cities = [
                {"id": n.id,
                 "lat": n.geolocation.latitude,
                 "lon": n.geolocation.longitude}
                for n in nodes
            ]
            edges = [
                {"source": r.start_node.id,
                 "target": r.end_node.id,
                 "distance": r.properties["sectionlength"]}
                for r in rels
            ]
            paths.append({
                "cities": cities,
                "edges": edges,
                "total_distance": rec["total_distance"]
            })
    return paths

def get_top_paths_cypher(source_id: str, target_id: str, limit: int = 3):
    """
    Fallback pure-Cypher method for k-shortest paths.
    """
    query = """
    MATCH path = (start:OperationPoint {id:$src})-[:SECTION*1..5]-(end:OperationPoint {id:$dst})
    WHERE ALL(n IN nodes(path)[1..-1] WHERE n.id <> $src)
    WITH path,
         reduce(acc=0, r IN relationships(path) | acc + r.sectionlength) AS total_distance
    ORDER BY total_distance ASC
    LIMIT $lim
    RETURN path, total_distance
    """
    paths = []
    with driver.session() as ses:
        for rec in ses.run(query, src=source_id, dst=target_id, lim=limit):
            cities = [
                {"id": n["id"],
                 "lat": n["geolocation"].latitude,
                 "lon": n["geolocation"].longitude}
                for n in rec["path"].nodes
            ]
            edges = [
                {"source": r.start_node["id"],
                 "target": r.end_node["id"],
                 "distance": r["sectionlength"]}
                for r in rec["path"].relationships
            ]
            paths.append({
                "cities": cities,
                "edges": edges,
                "total_distance": rec["total_distance"]
            })
    return paths

def get_top_paths(source_id: str, target_id: str, k: int = 3):
    """
    Primary entrypoint: try GDS first, fallback to Cypher.
    """
    try:
        return get_top_paths_gds(source_id, target_id, k)
    except Exception:
        return get_top_paths_cypher(source_id, target_id, k)

def close_driver():
    """Cleanly close the Neo4j driver."""
    driver.close()
